"""
Live retrieval-quality tests: they call the Gemini embedding API with the real key and use free-tier
quota (one embedding request per question), so they are skipped by default.

    python -m pytest -m live -q

Each question must have its expected section in the top 3, for embeddings and for the keyword fallback.
"""

import pytest

from chatbot import retrieval
from chatbot.retrieval import keyword_search, retrieve

pytestmark = pytest.mark.live

QUESTIONS = [
    ("Why does Russia include the Soviet Union?", {"counting_rules#countries-follow-noc-regions"}),
    ("Are the Winter Olympics included?", {"dataset#coverage-summer-games-1896-to-2016-only"}),
    ("How are relay medals counted?", {"counting_rules#team-medals-count-once"}),
    ("What is an NOC?", {"glossary#noc-national-olympic-committee"}),
    ("Why is the USA total different from the official medal table?",
     {"counting_rules#why-totals-can-differ-from-official-ioc-medal-tables"}),
    ("Who was the Unified Team?", {"glossary#unified-team-1992"}),
    ("How does this assistant work?", {"project#how-the-ask-the-data-assistant-answers"}),
    ("What was India's best Olympics?", {"findings#indias-best-games", "findings#indias-overall-record"}),
]
QUESTION_IDS = [question for question, _ in QUESTIONS]


@pytest.fixture(scope="module", autouse=True)
def fresh_caches():
    retrieval.clear_caches()
    yield
    retrieval.clear_caches()


@pytest.mark.parametrize("question, expected", QUESTIONS, ids=QUESTION_IDS)
def test_embedding_retrieval_has_expected_section_in_top_3(question, expected):
    result = retrieve(question, k=3)
    assert result.method == "embeddings", "the embedding call failed and retrieval fell back to keywords"
    top_ids = [chunk.id for chunk, _ in result.hits]
    assert expected & set(top_ids), top_ids


@pytest.mark.parametrize("question, expected", QUESTIONS, ids=QUESTION_IDS)
def test_keyword_fallback_has_expected_section_in_top_3(question, expected):
    top_ids = [chunk.id for chunk, _ in keyword_search(question, k=3)]
    assert expected & set(top_ids), top_ids
