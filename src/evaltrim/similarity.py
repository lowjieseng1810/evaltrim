"""Multi-factor similarity. Embeddings are optional; default is local TF-IDF + Jaccard."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TypedDict

from evaltrim.models import Behavior, RedundancyWeights, RunStats, TestCase
from evaltrim.normalize import char_ngrams, normalize_text


class PairScore(TypedDict):
    score: float
    semantic: float
    behavior_overlap: float
    expected_similarity: float
    historical_overlap: float
    shared: list[str]
    unique_left: list[str]
    unique_right: list[str]


_TOKEN_RE = re.compile(r"[a-z0-9_$]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def tokenize_normalized(text: str) -> list[str]:
    return tokenize(normalize_text(text)) or tokenize(text)


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    dot = sum(left.get(k, 0.0) * right.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in left.values()))
    nb = math.sqrt(sum(v * v for v in right.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class TfidfIndex:
    """In-memory TF-IDF for a closed corpus. Deterministic given document order."""

    def __init__(self, documents: Sequence[str], *, normalized: bool = False, char: bool = False) -> None:
        if char:
            self.docs = [char_ngrams(doc) for doc in documents]
        elif normalized:
            self.docs = [tokenize_normalized(doc) for doc in documents]
        else:
            self.docs = [tokenize(doc) for doc in documents]
        df: Counter[str] = Counter()
        for tokens in self.docs:
            df.update(set(tokens))
        n = max(len(self.docs), 1)
        self.idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in sorted(df.items())}
        self.vectors = [self._tfidf(tokens) for tokens in self.docs]

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        total = max(len(tokens), 1)
        return {term: (count / total) * self.idf.get(term, 0.0) for term, count in tf.items()}

    def pairwise(self, i: int, j: int) -> float:
        return cosine(self.vectors[i], self.vectors[j])


def content_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def historical_overlap(left: RunStats | None, right: RunStats | None) -> float:
    if left is None or right is None or left.runs <= 0 or right.runs <= 0:
        return 0.5
    fr_l = left.failure_rate or 0.0
    fr_r = right.failure_rate or 0.0
    return 1.0 - abs(fr_l - fr_r)


def behavior_overlap(left: Behavior, right: Behavior) -> tuple[float, list[str], list[str], list[str]]:
    a, b = set(left.atoms()), set(right.atoms())
    shared = sorted(a & b)
    unique_left = sorted(a - b)
    unique_right = sorted(b - a)
    return jaccard(a, b), shared, unique_left, unique_right


class SimilarityEngine:
    def __init__(
        self,
        tests: Sequence[TestCase],
        behaviors: Sequence[Behavior],
        weights: RedundancyWeights,
        cache: dict[str, float] | None = None,
        encoder: object | None = None,
    ) -> None:
        self.tests = list(tests)
        self.behaviors = list(behaviors)
        self.weights = weights
        self.cache = cache if cache is not None else {}
        self.encoder = encoder
        inputs = [t.input for t in tests]
        self.word_index = TfidfIndex(inputs, normalized=True)
        self.char_index = TfidfIndex(inputs, char=True)
        self.raw_index = TfidfIndex(inputs)
        self.expected_index = TfidfIndex([t.expected for t in tests], normalized=True)
        self._index = {t.id: i for i, t in enumerate(tests)}

    def _semantic(self, i: int, j: int) -> float:
        word = self.word_index.pairwise(i, j)
        char = self.char_index.pairwise(i, j)
        raw = self.raw_index.pairwise(i, j)
        lexical = 0.5 * word + 0.3 * char + 0.2 * raw
        if self.encoder is None:
            return lexical
        encoded = float(self.encoder.similarity(self.tests[i].input, self.tests[j].input))  # type: ignore[attr-defined]
        return 0.65 * lexical + 0.35 * encoded

    def pair_score(self, left_id: str, right_id: str) -> PairScore:
        i, j = self._index[left_id], self._index[right_id]
        key = content_hash("pair", *sorted((left_id, right_id)), self.tests[i].input, self.tests[j].input)
        if key in self.cache:
            # Cache stores the composite semantic channel only as a shortcut for embeddings.
            pass
        semantic = self._semantic(i, j)
        expected = self.expected_index.pairwise(i, j)
        overlap, shared, uniq_l, uniq_r = behavior_overlap(self.behaviors[i], self.behaviors[j])
        hist = historical_overlap(self.tests[i].run_stats, self.tests[j].run_stats)
        score = (
            self.weights.semantic * semantic
            + self.weights.behavior * overlap
            + self.weights.expected * expected
            + self.weights.historical * hist
        )
        rounded = round(float(score), 6)
        self.cache[key] = rounded
        return {
            "score": rounded,
            "semantic": round(semantic, 6),
            "behavior_overlap": round(overlap, 6),
            "expected_similarity": round(expected, 6),
            "historical_overlap": round(hist, 6),
            "shared": shared,
            "unique_left": uniq_l,
            "unique_right": uniq_r,
        }
