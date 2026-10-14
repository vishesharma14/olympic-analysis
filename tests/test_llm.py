"""
Offline tests for chatbot/llm.py: key lookup, model fallback and embeddings, with a mocked client.
No network and no real key are used.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from google.genai import errors

from chatbot import llm

pytestmark = pytest.mark.usefixtures("offline_gemini")

PRIMARY, FALLBACK = llm.DEFAULT_CHAT_MODELS
FAKE_KEY = "fake-test-key-not-a-real-secret-0000"


def api_error(code: int) -> errors.APIError:
    error_class = errors.ClientError if code < 500 else errors.ServerError
    return error_class(code, {"error": {"code": code, "message": "simulated", "status": "SIMULATED"}})


def fake_client(monkeypatch, generate=None, embed=None) -> list:
    """Installs a fake client; returns the list of (model, config) calls it receives."""
    calls = []

    def generate_content(*, model, contents, config=None):
        calls.append((model, config))
        return generate(model)

    def embed_content(*, model, contents, config=None):
        calls.append((model, config))
        return embed(contents)

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content, embed_content=embed_content))
    monkeypatch.setattr(llm, "_client", lambda: client)
    return calls


def failing_for(*models_and_codes):
    """A generate() side effect: raise the given error for each listed model, otherwise answer."""
    codes = dict(models_and_codes)

    def respond(model):
        if model in codes:
            raise api_error(codes[model])
        return f"answer from {model}"
    return respond


# generate(): fallback between chat models

def test_generate_uses_the_primary_model_when_it_works(monkeypatch):
    calls = fake_client(monkeypatch, generate=failing_for())
    assert llm.generate("hi") == f"answer from {PRIMARY}"
    assert [model for model, _ in calls] == [PRIMARY]


def test_generate_moves_to_the_fallback_model_on_429(monkeypatch):
    calls = fake_client(monkeypatch, generate=failing_for((PRIMARY, 429)))
    assert llm.generate("hi") == f"answer from {FALLBACK}"
    assert [model for model, _ in calls] == [PRIMARY, PRIMARY, FALLBACK]  # one retry, then the fallback


def test_generate_raises_quota_exceeded_when_both_models_fail(monkeypatch):
    calls = fake_client(monkeypatch, generate=failing_for((PRIMARY, 429), (FALLBACK, 503)))
    with pytest.raises(llm.QuotaExceeded, match="try again"):
        llm.generate("hi")
    assert [model for model, _ in calls] == [PRIMARY, PRIMARY, FALLBACK, FALLBACK]  # never more than 2 per model


def test_generate_skips_a_missing_model_without_retrying(monkeypatch):
    calls = fake_client(monkeypatch, generate=failing_for((PRIMARY, 404)))
    assert llm.generate("hi") == f"answer from {FALLBACK}"
    assert [model for model, _ in calls] == [PRIMARY, FALLBACK]


def test_generate_does_not_fall_back_on_a_bad_request(monkeypatch):
    calls = fake_client(monkeypatch, generate=failing_for((PRIMARY, 400)))
    with pytest.raises(llm.GeminiError, match="400") as raised:
        llm.generate("hi")
    assert not isinstance(raised.value, llm.QuotaExceeded)
    assert [model for model, _ in calls] == [PRIMARY]


def test_generate_errors_and_logs_contain_no_key_or_request(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    fake_client(monkeypatch, generate=failing_for((PRIMARY, 429), (FALLBACK, 429)))
    question = "private question text"
    with pytest.raises(llm.QuotaExceeded) as raised:
        llm.generate(question)
    for text in (str(raised.value), caplog.text):
        assert FAKE_KEY not in text and question not in text
    assert f"{PRIMARY} failed with 429" in caplog.text


def test_chat_and_embedding_models_can_be_overridden(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_MODELS", " model-a, model-b ,")
    monkeypatch.setenv("GEMINI_EMBED_MODEL", "embed-x")
    assert llm.chat_models() == ("model-a", "model-b")
    assert llm.embed_model() == "embed-x"


# Embeddings

def fake_embeddings(contents):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents])


def test_embed_query_returns_a_normalised_float32_vector_for_a_query(monkeypatch):
    calls = fake_client(monkeypatch, embed=fake_embeddings)
    vector = llm.embed_query("How are relay medals counted?")
    assert vector.dtype == np.float32 and vector.shape == (2,)
    np.testing.assert_allclose(vector, [0.6, 0.8], rtol=1e-6)
    (model, config), = calls
    assert model == llm.DEFAULT_EMBED_MODEL
    assert config.task_type == "RETRIEVAL_QUERY" and config.output_dimensionality == llm.EMBED_DIMENSIONS


def test_embed_documents_batches_and_normalises(monkeypatch):
    sizes = []
    calls = fake_client(monkeypatch, embed=lambda contents: sizes.append(len(contents)) or fake_embeddings(contents))
    vectors = llm.embed_documents([f"chunk {i}" for i in range(45)])
    assert sizes == [20, 20, 5]
    assert vectors.shape == (45, 2) and vectors.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-6)
    assert {config.task_type for _, config in calls} == {"RETRIEVAL_DOCUMENT"}


def test_embed_query_raises_quota_exceeded_on_429_without_retrying(monkeypatch):
    def quota_error(contents):
        raise api_error(429)
    calls = fake_client(monkeypatch, embed=quota_error)
    with pytest.raises(llm.QuotaExceeded):
        llm.embed_query("question")
    assert len(calls) == 1


# get_api_key()

def test_api_key_comes_from_the_environment_first(monkeypatch):
    llm.SECRETS_PATH.write_text('GEMINI_API_KEY = "from-file"\n', encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    assert llm.get_api_key() == FAKE_KEY


def test_api_key_falls_back_to_the_secrets_file():
    llm.SECRETS_PATH.write_text(f'GEMINI_API_KEY = "{FAKE_KEY}"\n', encoding="utf-8")
    assert llm.get_api_key() == FAKE_KEY


@pytest.mark.parametrize("secrets_file", [
    None,                                          # no secrets file at all
    f'OTHER_SECRET = "{FAKE_KEY}"\n',              # a file without GEMINI_API_KEY
    f'GEMINI_API_KEY = "{FAKE_KEY}\n',             # malformed TOML that contains a key-like value
], ids=["no-file", "other-secret", "malformed-toml"])
def test_missing_api_key_error_contains_no_secret(secrets_file):
    if secrets_file is not None:
        llm.SECRETS_PATH.write_text(secrets_file, encoding="utf-8")
    with pytest.raises(llm.MissingAPIKey) as raised:
        llm.get_api_key()
    message = str(raised.value)
    assert message.startswith("GEMINI_API_KEY is not set")
    assert FAKE_KEY not in message and FAKE_KEY not in repr(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None
