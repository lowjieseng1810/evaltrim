"""Multi-factor similarity. Embeddings are optional; default is local TF-IDF + Jaccard."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence

from evaltrim.models import Behavior, RedundancyWeights, RunStats, TestCase

_TOKEN_RE = re.compile(r"[a-z0-9_$]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


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

    def __init__(self, documents: Sequence[str]) -> None:
        self.docs = [tokenize(doc) for doc in documents]
        df: Counter[str] = Counter()
        for tokens in self.docs:
            df.update(set(tokens))
        n = len(self.docs)
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
    ) -> None:
        self.tests = list(tests)
        self.behaviors = list(behaviors)
        self.weights = weights
        self.cache = cache if cache is not None else {}
        self.input_index = TfidfIndex([t.input for t in tests])
        self.expected_index = TfidfIndex([t.expected for t in tests])
        self._index = {t.id: i for i, t in enumerate(tests)}

    def pair_score(self, left_id: str, right_id: str) -> dict[str, float | list[str]]:
        i, j = self._index[left_id], self._index[right_id]
        key = content_hash("pair", *sorted((left_id, right_id)), self.tests[i].input, self.tests[j].input)
        semantic = self.input_index.pairwise(i, j)
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
