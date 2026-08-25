"""Generate plausible comparison pairs without a full O(n²) scan on large suites."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from evaltrim.models import Behavior, TestCase
from evaltrim.normalize import normalize_text
from evaltrim.similarity import tokenize


class CandidatePairGenerator:
    """Layer 1 blocking: exact hash, behavior signature, inverted-index neighbors."""

    def __init__(self, *, full_pairwise_limit: int = 200, neighbor_k: int = 40) -> None:
        self.full_pairwise_limit = full_pairwise_limit
        self.neighbor_k = neighbor_k

    def pairs(self, tests: Sequence[TestCase], behaviors: Sequence[Behavior]) -> list[tuple[int, int]]:
        n = len(tests)
        if n <= 1:
            return []
        if n <= self.full_pairwise_limit:
            return [(i, j) for i in range(n) for j in range(i + 1, n)]

        found: set[tuple[int, int]] = set()

        def add(i: int, j: int) -> None:
            if i == j:
                return
            a, b = (i, j) if i < j else (j, i)
            found.add((a, b))

        # Exact normalized-input groups.
        by_hash: dict[str, list[int]] = defaultdict(list)
        for i, test in enumerate(tests):
            by_hash[normalize_text(test.input)].append(i)
        for group in by_hash.values():
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])

        # Same behavior signature groups (capped).
        by_sig: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for i, behavior in enumerate(behaviors):
            by_sig[tuple(behavior.atoms())].append(i)
        for group in by_sig.values():
            if len(group) > 80:
                group = group[:80]
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])

        # Inverted index on normalized tokens (rare-ish terms first).
        postings: dict[str, list[int]] = defaultdict(list)
        tokens_by_doc = [tokenize(normalize_text(t.input) + " " + t.input.lower()) for t in tests]
        for i, toks in enumerate(tokens_by_doc):
            for term in set(toks):
                postings[term].append(i)
        df = {term: len(ids) for term, ids in postings.items()}

        for i, toks in enumerate(tokens_by_doc):
            scores: dict[int, float] = defaultdict(float)
            ranked_terms = sorted(set(toks), key=lambda t: df.get(t, n))
            for term in ranked_terms[:12]:
                idf = 1.0 / max(df.get(term, 1), 1)
                if df.get(term, n) > n * 0.4:
                    continue
                for j in postings[term]:
                    if j != i:
                        scores[j] += idf
            neighbors = sorted(scores, key=lambda j: (-scores[j], j))[: self.neighbor_k]
            for j in neighbors:
                add(i, j)

        return sorted(found)
