import pytest

from chatbot import llm, retrieval


class NetworkDisabled(RuntimeError):
    pass


@pytest.fixture
def offline_gemini(monkeypatch, tmp_path):
    """No key, no settings and no network: Gemini settings come only from what a test sets itself."""
    for name in ("GEMINI_API_KEY", "GEMINI_CHAT_MODELS", "GEMINI_EMBED_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "SECRETS_PATH", tmp_path / "no-secrets.toml")
    monkeypatch.setattr(llm, "_streamlit_secret", lambda name: None)

    def no_network():
        raise NetworkDisabled("offline tests must not call Gemini")

    monkeypatch.setattr(llm, "_client", no_network)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    retrieval.clear_caches()
    yield
    retrieval.clear_caches()
