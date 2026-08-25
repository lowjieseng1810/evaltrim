"""Multi-factor similarity. Embeddings are optional; default is local TF-IDF + Jaccard."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TypedDict

from evaltrim.embeddings import HashingNgramEncoder
from evaltrim.models import Behavior, RedundancyWeights, RunStats, TestCase
from evaltrim.normalize import char_ngrams, extract_amounts, normalize_text


class PairScore(TypedDict):
    score: float
    semantic: float
    behavior_overlap: float
    expected_similarity: float
    historical_overlap: float
    shared: list[str]
    unique_left: list[str]
    unique_right: list[str]
    semantic_confidence: float
    behavior_confidence: float
    combined_confidence: float
    semantic_tier: str


_EXCEPTION_MARKERS = {
    "but",
    "however",
    "already",
    "instead",
    "except",
    "unless",
    "never",
    "credit",
}


def _exception_penalty(left: str, right: str) -> float:
    """Down-weight pairs that share a request but add a contradicting clause."""
    a = set(tokenize_normalized(left)) | set(tokenize(left))
    b = set(tokenize_normalized(right)) | set(tokenize(right))
    left_x = bool(a & _EXCEPTION_MARKERS)
    right_x = bool(b & _EXCEPTION_MARKERS)
    if left_x != right_x:
        return 0.72
    extra = (a - b) | (b - a)
    if extra & {"credit", "already", "instead"}:
        return 0.70
    return 1.0


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
    """Unknown history is treated as agreement (1.0), not a 0.5 penalty.

    Missing run stats must not drag otherwise-identical paraphrases below MERGE.
    """
    if left is None or right is None or left.runs <= 0 or right.runs <= 0:
        return 1.0
    fr_l = left.failure_rate or 0.0
    fr_r = right.failure_rate or 0.0
    return 1.0 - abs(fr_l - fr_r)


def _tf_vector(tokens: Sequence[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = max(sum(counts.values()), 1)
    return {term: count / total for term, count in counts.items()}


def _prefix_jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    """Jaccard that treats tokens sharing a 4-char stem as matches (duplicate/duplication)."""
    a, b = list(left), list(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    used_b = [False] * len(b)
    matched = 0
    for tok in a:
        stem = tok[:4] if len(tok) >= 4 else tok
        for i, other in enumerate(b):
            if used_b[i]:
                continue
            other_stem = other[:4] if len(other) >= 4 else other
            if tok == other or stem == other_stem:
                used_b[i] = True
                matched += 1
                break
    union = len(a) + len(b) - matched
    return matched / union if union else 1.0


def amount_agreement(left: str, right: str) -> float:
    a, b = extract_amounts(left), extract_amounts(right)
    if not a and not b:
        return 0.5
    if not a or not b:
        return 0.0
    sa, sb = {round(x, 2) for x in a}, {round(x, 2) for x in b}
    return jaccard((str(x) for x in sa), (str(x) for x in sb))


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
        self.use_char = len(tests) <= 400
        self.char_index = TfidfIndex(inputs, char=True) if self.use_char else None
        self.raw_index = TfidfIndex(inputs)
        self.expected_index = TfidfIndex([t.expected for t in tests], normalized=True)
        self._index = {t.id: i for i, t in enumerate(tests)}
        self._norm_tokens = [tokenize_normalized(t.input) for t in tests]
        self._tf_vecs = [_tf_vector(toks) for toks in self._norm_tokens]
        self._tier2 = HashingNgramEncoder(dims=128) if len(tests) <= 400 else None

    def _lexical(self, i: int, j: int) -> float:
        left, right = self.tests[i].input, self.tests[j].input
        n_left = self._norm_tokens[i]
        n_right = self._norm_tokens[j]
        norm_eq = normalize_text(left) == normalize_text(right) and bool(normalize_text(left))
        jac = _prefix_jaccard(n_left, n_right)
        tf_cos = cosine(self._tf_vecs[i], self._tf_vecs[j])
        word = self.word_index.pairwise(i, j)
        char = self.char_index.pairwise(i, j) if self.char_index is not None else jac
        raw = self.raw_index.pairwise(i, j)
        amounts = amount_agreement(left, right)
        content_l = [t for t in n_left if len(t) >= 4 or t.startswith("amt_") or "_" in t]
        content_r = [t for t in n_right if len(t) >= 4 or t.startswith("amt_") or "_" in t]
        content = _prefix_jaccard(content_l, content_r) if (content_l or content_r) else jac
        lexical = 0.30 * jac + 0.18 * tf_cos + 0.14 * char + 0.12 * word + 0.10 * raw + 0.16 * content
        if amounts >= 0.99 and jac >= 0.45:
            lexical = max(lexical, 0.88)
        if jac >= 0.75:
            lexical = max(lexical, 0.86)
        if content >= 0.5 and jac >= 0.32:
            lexical = max(lexical, 0.84)
        shared_content = set(content_l) & set(content_r)
        if len(shared_content) >= 2 and jac >= 0.35:
            lexical = max(lexical, 0.85)
        rare_shared = [t for t in set(n_left) & set(n_right) if len(t) >= 8 or "_" in t]
        if rare_shared and jac >= 0.28:
            lexical = max(lexical, 0.86)
        if norm_eq:
            lexical = max(lexical, 0.97)
        lexical = min(1.0, 0.82 * lexical + 0.18 * (amounts if amounts != 0.5 else lexical))
        penalty = _exception_penalty(left, right)
        if penalty < 1.0:
            # Do not let rare-token boosts override a contradicting clause.
            lexical = min(lexical * penalty, 0.78)
        return lexical

    def _semantic(self, i: int, j: int) -> tuple[float, str, float]:
        """Return (score, tier_used, semantic_confidence). Tier 3 is optional encoder."""
        left, right = self.tests[i].input, self.tests[j].input
        tier1 = self._lexical(i, j)
        if self._tier2 is None and self.encoder is None:
            return tier1, "tier1_lexical", 0.7
        if self._tier2 is None:
            enc = self.encoder
            assert enc is not None
            encoded = float(enc.similarity(left, right))  # type: ignore[attr-defined]
            return min(1.0, 0.70 * tier1 + 0.30 * encoded), "tier3_optional", 0.75
        tier2 = float(self._tier2.similarity(left, right))
        blended = min(1.0, 0.86 * tier1 + 0.14 * tier2)
        agreement = 1.0 - min(1.0, abs(tier1 - tier2))
        if self.encoder is None:
            return blended, "tier2_local", round(0.55 + 0.45 * agreement, 4)
        encoded = float(self.encoder.similarity(left, right))  # type: ignore[attr-defined]
        mixed = min(1.0, 0.62 * blended + 0.38 * encoded)
        return mixed, "tier3_optional", round(0.60 + 0.40 * agreement, 4)

    def pair_score(self, left_id: str, right_id: str) -> PairScore:
        i, j = self._index[left_id], self._index[right_id]
        key = content_hash("pair", *sorted((left_id, right_id)), self.tests[i].input, self.tests[j].input)
        semantic, tier, sem_conf = self._semantic(i, j)
        expected = self.expected_index.pairwise(i, j)
        exp_l, exp_r = self.tests[i].expected, self.tests[j].expected
        if normalize_text(exp_l) == normalize_text(exp_r) and normalize_text(exp_l):
            expected = max(expected, 0.99)
        else:
            expected = max(expected, _prefix_jaccard(tokenize_normalized(exp_l), tokenize_normalized(exp_r)))
        overlap, shared, uniq_l, uniq_r = behavior_overlap(self.behaviors[i], self.behaviors[j])
        hist = historical_overlap(self.tests[i].run_stats, self.tests[j].run_stats)
        score = (
            self.weights.semantic * semantic
            + self.weights.behavior * overlap
            + self.weights.expected * expected
            + self.weights.historical * hist
        )
        behavior_conf = round(0.5 * overlap + 0.5 * (1.0 if not uniq_l and not uniq_r else 0.35), 4)
        combined = round(0.35 * sem_conf + 0.65 * behavior_conf, 4)
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
            "semantic_confidence": sem_conf,
            "behavior_confidence": behavior_conf,
            "combined_confidence": combined,
            "semantic_tier": tier,
        }
