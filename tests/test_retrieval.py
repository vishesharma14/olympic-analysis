"""
Offline tests for chatbot/retrieval.py and the committed index. No network and no real key are used.
"""

import logging

import numpy as np
import pytest

from chatbot import llm, retrieval
from chatbot.knowledge import load_chunks
from chatbot.retrieval import Index, keyword_search, load_index, retrieve, text_hash

pytestmark = pytest.mark.usefixtures("offline_gemini")

CHUNKS = load_chunks()
RELAY_QUESTION = "how are relay medals counted"


# The committed index

def test_committed_index_matches_the_current_notes():
    with np.load(retrieval.INDEX_PATH, allow_pickle=False) as data:
        assert data["ids"].tolist() == [chunk.id for chunk in CHUNKS]
        assert data["text_sha256"].tolist() == [text_hash(chunk.text) for chunk in CHUNKS]
        assert data["model"].item() == llm.DEFAULT_EMBED_MODEL
        assert int(data["dimensions"]) == llm.EMBED_DIMENSIONS
        vectors = data["vectors"]
    assert vectors.shape == (len(CHUNKS), llm.EMBED_DIMENSIONS) and vectors.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-5)
    assert load_index() is not None


def test_index_is_rejected_when_a_note_changed(tmp_path, caplog):
    with np.load(retrieval.INDEX_PATH, allow_pickle=False) as data:
        fields = {name: data[name] for name in data.files}
    fields["text_sha256"] = fields["text_sha256"].copy()
    fields["text_sha256"][0] = text_hash("an older version of the note")
    stale = tmp_path / "stale.npz"
    np.savez(stale, **fields)
    with caplog.at_level(logging.WARNING):
        assert load_index(stale) is None
    assert "python -m chatbot.build_index" in caplog.text


def test_index_is_rejected_when_the_embedding_model_changed(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_EMBED_MODEL", "some-other-embedding-model")
    with caplog.at_level(logging.WARNING):
        assert load_index() is None
    assert "some-other-embedding-model" in caplog.text


# Cosine ranking (fake embedder)

def test_cosine_ranking_with_a_fake_embedder(monkeypatch):
    vectors = np.eye(len(CHUNKS), dtype=np.float32)  # chunk i points along axis i
    monkeypatch.setattr(retrieval, "load_index", lambda: Index(vectors, [chunk.id for chunk in CHUNKS]))
    calls = []

    def fake_embed_query(text):
        calls.append(text)
        query = np.zeros(len(CHUNKS), dtype=np.float32)
        query[5], query[2] = 0.8, 0.6  # closest to chunk 5, then chunk 2
        return query

    monkeypatch.setattr(llm, "embed_query", fake_embed_query)
    result = retrieve("any question", k=3)
    assert result.method == "embeddings"
    assert [chunk.id for chunk, _ in result.hits] == [CHUNKS[5].id, CHUNKS[2].id, CHUNKS[0].id]
    assert [round(score, 6) for _, score in result.hits] == [0.8, 0.6, 0.0]
    retrieve("any   question", k=3)  # same question after whitespace clean-up: served from the LRU cache
    assert calls == ["any question"]


# Keyword fallback

def test_keyword_fallback_ranks_the_team_medal_rule_first_for_relays():
    assert keyword_search(RELAY_QUESTION)[0][0].id == "counting_rules#team-medals-count-once"


def test_keyword_fallback_finds_indias_record_for_hockey():
    assert "findings#indias-overall-record" in [chunk.id for chunk, _ in keyword_search("India hockey medals", k=3)]


def test_retrieve_falls_back_to_keywords_when_embedding_fails():
    # offline_gemini makes every Gemini call fail, as a missing key or network outage would.
    result = retrieve(RELAY_QUESTION)
    assert result.method == "keywords"
    assert result.hits[0][0].id == "counting_rules#team-medals-count-once"


def test_retrieve_uses_keywords_without_embedding_when_the_index_is_stale(monkeypatch):
    monkeypatch.setattr(retrieval, "load_index", lambda: None)
    monkeypatch.setattr(llm, "embed_query", lambda text: pytest.fail("a stale index must not trigger an embedding"))
    assert retrieve(RELAY_QUESTION).method == "keywords"


def test_keyword_search_ignores_questions_without_known_words():
    assert keyword_search("the of and") == []
