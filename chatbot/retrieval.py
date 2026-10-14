"""
retrieval.py
------------
Finds the knowledge chunks most relevant to a question.

    retrieve(question, k=4) -> Retrieval(hits=[(Chunk, score), ...], method="embeddings" or "keywords")

By default the question is embedded with Gemini and chunks are ranked by cosine similarity against
the prebuilt index (chatbot/index/knowledge_index.npz, written by python -m chatbot.build_index).
If the question cannot be embedded (quota, network, missing key), or the index does not match the
current notes and embedding model, chunks are ranked by BM25 keyword scoring instead, so the
assistant keeps working without embeddings.
"""

import hashlib
import logging
import math
import re
from collections import Counter
from functools import cache, lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np

from chatbot import llm
from chatbot.knowledge import Chunk, load_chunks

INDEX_PATH = Path(__file__).resolve().parent / "index" / "knowledge_index.npz"
QUERY_CACHE_SIZE = 256

log = logging.getLogger(__name__)


class Retrieval(NamedTuple):
    hits: list[tuple[Chunk, float]]  # best first; cosine similarity for embeddings, BM25 score for keywords
    method: str  # "embeddings" or "keywords"


class Index(NamedTuple):
    vectors: np.ndarray  # one L2-normalised row per chunk, in load_chunks() order
    ids: list[str]


def retrieve(question: str, k: int = 4) -> Retrieval:
    question = " ".join(question.split())
    index = _index()
    if index is not None:
        try:
            query = _query_vector(question)
        except Exception as error:  # quota, network or missing key: degrade to keywords
            log.warning("Could not embed the question (%s); using keyword retrieval.", type(error).__name__)
        else:
            return Retrieval(cosine_search(query, index.vectors, _chunks(), k), "embeddings")
    return Retrieval(keyword_search(question, k), "keywords")


def cosine_search(query: np.ndarray, vectors: np.ndarray, chunks: list[Chunk], k: int) -> list[tuple[Chunk, float]]:
    """Ranks chunks by cosine similarity; vectors and query are already L2-normalised."""
    scores = vectors @ query
    best = np.argsort(-scores, kind="stable")[:k]
    return [(chunks[i], float(scores[i])) for i in best]


def keyword_search(question: str, k: int = 4) -> list[tuple[Chunk, float]]:
    """Ranks chunks by BM25 over their words; returns only chunks that share a word with the question."""
    return _keyword_index().search(question, k)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_index(path: Path = INDEX_PATH) -> Index | None:
    """The saved index, or None (with a warning) if it is missing or no longer matches the notes and model."""
    chunks = load_chunks()
    try:
        with np.load(path, allow_pickle=False) as data:
            vectors, ids, hashes = data["vectors"], data["ids"].tolist(), data["text_sha256"].tolist()
            model, dimensions = data["model"].item(), int(data["dimensions"])
    except (OSError, KeyError, ValueError) as error:
        log.warning("No usable knowledge index (%s); using keyword retrieval. Run: python -m chatbot.build_index",
                    type(error).__name__)
        return None
    problems = []
    if model != llm.embed_model():
        problems.append(f"built with {model}, but the embedding model is {llm.embed_model()}")
    if dimensions != llm.EMBED_DIMENSIONS or vectors.shape != (len(ids), dimensions):
        problems.append(f"{dimensions} dimensions, expected {llm.EMBED_DIMENSIONS}")
    if ids != [chunk.id for chunk in chunks] or hashes != [text_hash(chunk.text) for chunk in chunks]:
        problems.append("the knowledge notes have changed since it was built")
    if problems:
        log.warning("The knowledge index is out of date (%s); using keyword retrieval. Run: python -m chatbot.build_index",
                    "; ".join(problems))
        return None
    return Index(vectors.astype(np.float32), ids)


def clear_caches() -> None:
    """Forgets the loaded notes, index and query embeddings (after rebuilding the index, or in tests)."""
    for cached in (_chunks, _index, _keyword_index, _query_vector):
        cached.cache_clear()


@cache
def _chunks() -> list[Chunk]:
    return load_chunks()


@cache
def _index() -> Index | None:
    return load_index()


@lru_cache(maxsize=QUERY_CACHE_SIZE)
def _query_vector(question: str) -> np.ndarray:
    vector = llm.embed_query(question)
    vector.setflags(write=False)  # shared by every caller through the cache
    return vector


# Keyword fallback (BM25)

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset("""
    a about all an and any are as at be been but by can did do does for from had has have how i if in into
    is it its me my no not of on or our so than that the their them then there these they this those to
    was we were what when where which who whom why will with you your
""".split())


def tokenize(text: str) -> list[str]:
    """Lower-cased words without stopwords, reduced to a crude stem ("counted", "counts" -> "count")."""
    return [_stem(word) for word in _WORD.findall(text.lower()) if len(word) > 1 and word not in _STOPWORDS]


def _stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[:-len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


class _KeywordIndex:
    K1, B = 1.5, 0.75
    HEADING_BONUS = 1.0  # a question word in the section heading adds its idf once more

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        # The heading is counted twice (it is also in the text) because it names the section's subject.
        self.term_counts = [Counter(tokenize(f"{chunk.heading} {chunk.text}")) for chunk in chunks]
        self.heading_terms = [set(tokenize(chunk.heading)) for chunk in chunks]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_length = sum(self.lengths) / len(self.lengths)
        document_frequency = Counter(term for counts in self.term_counts for term in counts)
        self.idf = {term: math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5)) for term, df in document_frequency.items()}

    def search(self, question: str, k: int) -> list[tuple[Chunk, float]]:
        terms = set(tokenize(question)) & self.idf.keys()
        scored = []
        for chunk, counts, length, heading in zip(self.chunks, self.term_counts, self.lengths, self.heading_terms):
            norm = self.K1 * (1 - self.B + self.B * length / self.average_length)
            score = sum(self.idf[t] * counts[t] * (self.K1 + 1) / (counts[t] + norm) for t in terms if t in counts)
            # BM25 saturates repeated words, so a match in the heading, which names the section's subject,
            # is added as a separate field bonus.
            score += self.HEADING_BONUS * sum(self.idf[t] for t in terms & heading)
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda hit: hit[1], reverse=True)[:k]


@cache
def _keyword_index() -> _KeywordIndex:
    return _KeywordIndex(_chunks())
