"""
llm.py
------
The only module that talks to Gemini, through the official Google Gen AI SDK (google-genai).

    get_api_key()          GEMINI_API_KEY from the environment, Streamlit secrets or .streamlit/secrets.toml
    embed_documents(texts) L2-normalised float32 vectors for knowledge chunks
    embed_query(text)      L2-normalised float32 vector for a question
    generate(contents)     a chat completion, falling back to the next model on quota or overload errors
                           (each model gets its own thinking level when THINKING_LEVELS has one)

A chat model that is out of quota or overloaded (429 or 503 after its retry) is skipped by this
process for COOLDOWN_S seconds, and a model that does not exist (404) is skipped for good, so later
calls go straight to a model that works. The skip list is shared by all threads (Streamlit serves
each session on its own thread).

The key is read at runtime only. It never appears in a log line or an exception message, and
neither does a request body: errors are reported by model ID and HTTP status code.
"""

import logging
import math
import os
import sys
import threading
import time
import tomllib
from collections import Counter
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import httpx
import numpy as np
from google import genai
from google.genai import errors, types

ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

# Free-tier models, chosen with python -m chatbot.list_models. Override with GEMINI_CHAT_MODELS
# (comma-separated, tried in order) and GEMINI_EMBED_MODEL. Checked in October 2026 and left out:
# gemini-2.5-flash-lite (404, no longer available to new keys) and gemini-3.7-flash (400: rejects the
# agent's MINIMAL thinking level, not probed with LOW).
DEFAULT_CHAT_MODELS = (
    "gemini-3.5-flash-lite",  # Gemini 3.5 Flash Lite: 15 requests/min, 250K tokens/min, 500 requests/day
    "gemini-3.1-flash-lite",  # Gemini 3.1 Flash Lite: same limits, used when the first is out of quota
    "gemini-3.8-flash",       # Gemini 3.8 Flash: the last resort (3.1 returned 503 on every probe so far)
)
# Thinking levels for models that reject the one in the caller's config. gemini-3.8-flash returns 400
# for MINIMAL, the agent's level; LOW is its lowest accepted level (probed in October 2026).
THINKING_LEVELS = {"gemini-3.8-flash": types.ThinkingLevel.LOW}
DEFAULT_EMBED_MODEL = "gemini-embedding-001"  # Gemini Embedding 1: 100 requests/min, 30K tokens/min, 1K requests/day
EMBED_DIMENSIONS = 768

# Embedding requests are batched to stay well inside the free tier's 100 requests and 30,000 tokens a minute.
EMBED_BATCH_SIZE = 20
EMBED_BATCH_MAX_CHARS = 24_000  # about 6,000 tokens at roughly 4 characters per token
EMBED_BATCH_INTERVAL_S = 1.0

TRANSIENT_CODES = frozenset({429, 500, 503, 504})  # quota, internal error, overload, deadline: retry once, then next model
MISSING_MODEL_CODE = 404  # a retired or unknown model ID: go straight to the next model
COOLDOWN_CODES = frozenset({429, 503})  # still failing after the retry: skip the model for COOLDOWN_S
COOLDOWN_S = 300.0
RETRY_BACKOFF_S = 2.0
REQUEST_TIMEOUT_MS = 60_000

log = logging.getLogger(__name__)
usage = Counter()  # API requests made by this process, keyed by model ID

_clock = time.monotonic  # replaced by a fake clock in tests
_skipped_until: dict[str, float] = {}  # chat model ID -> _clock() time until which generate() skips it
_skip_lock = threading.Lock()


class GeminiError(RuntimeError):
    """A Gemini call failed. The message is short and safe to show to users."""


class MissingAPIKey(GeminiError):
    pass


class QuotaExceeded(GeminiError):
    pass


def get_setting(name: str) -> str | None:
    """Reads a setting from the environment, then Streamlit secrets, then .streamlit/secrets.toml."""
    value = os.environ.get(name) or _streamlit_secret(name) or _secrets_file_value(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)  # a TOML number such as CHAT_DAILY_LIMIT = 300
    return value.strip() if isinstance(value, str) and value.strip() else None


def get_api_key() -> str:
    key = get_setting("GEMINI_API_KEY")
    if key is None:
        raise MissingAPIKey(
            "GEMINI_API_KEY is not set. Add it to .streamlit/secrets.toml locally or to Streamlit Cloud Secrets.")
    return key


def chat_models() -> tuple[str, ...]:
    configured = get_setting("GEMINI_CHAT_MODELS")
    if configured:
        return tuple(model.strip() for model in configured.split(",") if model.strip())
    return DEFAULT_CHAT_MODELS


def embed_model() -> str:
    return get_setting("GEMINI_EMBED_MODEL") or DEFAULT_EMBED_MODEL


def embed_documents(texts: Sequence[str]) -> np.ndarray:
    """Embeds knowledge chunks for retrieval; returns an array of shape (len(texts), EMBED_DIMENSIONS)."""
    vectors = []
    for number, batch in enumerate(_batches(list(texts))):
        if number:
            time.sleep(EMBED_BATCH_INTERVAL_S)
        vectors.extend(_embed(batch, "RETRIEVAL_DOCUMENT", retry=True))
    return _normalise(np.array(vectors, dtype=np.float32))


def embed_query(text: str) -> np.ndarray:
    """Embeds a question for retrieval; fails fast (no retry) so the caller can fall back to keywords."""
    return _normalise(np.array(_embed([text], "RETRIEVAL_QUERY", retry=False), dtype=np.float32))[0]


def generate(contents, config: types.GenerateContentConfig | None = None,
             models: Sequence[str] | None = None) -> types.GenerateContentResponse:
    """Calls the chat models in order; moves to the next one on quota, overload or a missing model.

    Models that recently ran out of quota or do not exist are skipped (see the module docstring).
    """
    for model in models or chat_models():
        if _is_skipped(model):
            log.info("Skipping Gemini model %s: it failed recently", model)
            continue
        for attempt in (1, 2):
            try:
                usage[model] += 1
                return _client().models.generate_content(model=model, contents=contents,
                                                         config=_config_for(model, config))
            except (errors.APIError, httpx.HTTPError) as error:
                code = _failure_code(error)
            log.warning("Gemini model %s failed with %s (attempt %d)", model, code, attempt)
            if code == MISSING_MODEL_CODE:
                _skip(model, math.inf)
                break
            if not _is_transient(code):
                raise GeminiError(f"The Gemini request failed ({code}).")
            if attempt == 1:
                time.sleep(RETRY_BACKOFF_S)
            elif code in COOLDOWN_CODES:
                _skip(model, COOLDOWN_S)
    raise QuotaExceeded("The assistant's Gemini models are busy or out of quota right now. "
                        "Please try again in a few minutes.")


def _config_for(model: str, config: types.GenerateContentConfig | None) -> types.GenerateContentConfig | None:
    """config with the model's own thinking level from THINKING_LEVELS; the caller's config is not changed."""
    level = THINKING_LEVELS.get(model)
    if config is None or config.thinking_config is None or level is None:
        return config
    return config.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level=level)})


def clear_skipped_models() -> None:
    """Forgets which chat models generate() is skipping (in tests, or after changing the key)."""
    with _skip_lock:
        _skipped_until.clear()


def _is_skipped(model: str) -> bool:
    with _skip_lock:
        return _clock() < _skipped_until.get(model, -math.inf)


def _skip(model: str, seconds: float) -> None:
    with _skip_lock:
        _skipped_until[model] = _clock() + seconds
    log.warning("Skipping Gemini model %s %s", model,
                "for the rest of this process" if seconds == math.inf else f"for {seconds:g} seconds")


@cache
def _client() -> genai.Client:
    # retry_options is left unset, so the SDK makes exactly one attempt per call and generate() owns retries.
    return genai.Client(api_key=get_api_key(), http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))


def _embed(texts: list[str], task_type: str, retry: bool) -> list[list[float]]:
    model = embed_model()
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIMENSIONS)
    for attempt in (1, 2):
        try:
            usage[model] += 1
            response = _client().models.embed_content(model=model, contents=texts, config=config)
            return [embedding.values for embedding in response.embeddings]
        except (errors.APIError, httpx.HTTPError) as error:
            code = _failure_code(error)
        log.warning("Gemini embedding model %s failed with %s (attempt %d)", model, code, attempt)
        if not (retry and attempt == 1 and _is_transient(code)):
            break
        time.sleep(RETRY_BACKOFF_S)
    if code == 429:
        raise QuotaExceeded("The Gemini embedding quota is used up for now.")
    raise GeminiError(f"The Gemini embedding request failed ({code}).")


def _failure_code(error: Exception) -> int | str:
    """The HTTP status of an API error, or the exception name of a network failure or timeout."""
    return error.code if isinstance(error, errors.APIError) else type(error).__name__


def _is_transient(code: int | str) -> bool:
    return code in TRANSIENT_CODES or isinstance(code, str)


def _batches(texts: list[str]):
    batch, chars = [], 0
    for text in texts:
        if batch and (len(batch) == EMBED_BATCH_SIZE or chars + len(text) > EMBED_BATCH_MAX_CHARS):
            yield batch
            batch, chars = [], 0
        batch.append(text)
        chars += len(text)
    if batch:
        yield batch


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.where(norms == 0, 1, norms)).astype(np.float32)


def _streamlit_secret(name: str) -> str | None:
    """st.secrets, only when Streamlit is already loaded (the app); CLI scripts and tests use the file instead."""
    streamlit = sys.modules.get("streamlit")
    if streamlit is None:
        return None
    try:
        return streamlit.secrets[name]
    except Exception:
        return None


def _secrets_file_value(name: str) -> str | None:
    try:
        with open(SECRETS_PATH, "rb") as file:
            return tomllib.load(file).get(name)
    except (OSError, tomllib.TOMLDecodeError):
        return None
