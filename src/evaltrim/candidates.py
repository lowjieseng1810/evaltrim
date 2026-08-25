"""Generate plausible comparison pairs without a full O(n²) scan on large suites."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from evaltrim.embeddings import SemanticEncoder
from evaltrim.models import Behavior, TestCase
from evaltrim.normalize import normalize_text
from evaltrim.similarity import tokenize


class CandidatePairGenerator:
    """Layered blocking: exact hash → lexical → behavior → TF/n-gram → optional embeddings.

    Similarity may create candidates. It never authorizes RETIRE by itself.
    """

    def __init__(
        self,
        *,
        full_pairwise_limit: int = 200,
        neighbor_k: int = 40,
        max_block_df: int = 48,
    ) -> None:
        self.full_pairwise_limit = full_pairwise_limit
        self.neighbor_k = neighbor_k
        self.max_block_df = max_block_df

    def pairs(
        self,
        tests: Sequence[TestCase],
        behaviors: Sequence[Behavior],
        *,
        encoder: SemanticEncoder | None = None,
    ) -> list[tuple[int, int]]:
        n = len(tests)
        if n <= 1:
            return []
        if n <= self.full_pairwise_limit:
            return [(i, j) for i in range(n) for j in range(i + 1, n)]
        neighbor_k = self.neighbor_k
        if n > 5000:
            neighbor_k = min(neighbor_k, 4)
        elif n > 2000:
            neighbor_k = min(neighbor_k, 8)

        found: set[tuple[int, int]] = set()

        def add(i: int, j: int) -> None:
            if i == j:
                return
            a, b = (i, j) if i < j else (j, i)
            found.add((a, b))

        # 1. Exact / hash dedup on normalized input.
        by_hash: dict[str, list[int]] = defaultdict(list)
        for i, test in enumerate(tests):
            by_hash[normalize_text(test.input)].append(i)
        for group in by_hash.values():
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])

        # 2. Lexical blocking: same normalized prefix (near-dup wording).
        by_prefix: dict[str, list[int]] = defaultdict(list)
        for i, test in enumerate(tests):
            prefix = normalize_text(test.input)[:24]
            if prefix:
                by_prefix[prefix].append(i)
        for group in by_prefix.values():
            if len(group) > 60:
                group = group[:60]
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])

        # 3. Behavior-based blocking (full signature and domain+action).
        by_sig: dict[tuple[str, ...], list[int]] = defaultdict(list)
        by_da: dict[tuple[str, str], list[int]] = defaultdict(list)
        for i, behavior in enumerate(behaviors):
            by_sig[tuple(behavior.atoms())].append(i)
            by_da[(behavior.domain, behavior.action)].append(i)
        for group in by_sig.values():
            if len(group) > 80:
                group = group[:80]
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])
        for group in by_da.values():
            if len(group) > 50:
                group = group[:50]
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    add(group[a], group[b])

        # 4. TF / n-gram inverted-index retrieval.
        postings: dict[str, list[int]] = defaultdict(list)
        tokens_by_doc = [tokenize(normalize_text(t.input) + " " + t.input.lower()) for t in tests]
        for i, toks in enumerate(tokens_by_doc):
            for term in set(toks):
                postings[term].append(i)
        df = {term: len(ids) for term, ids in postings.items()}
        df_cap = min(self.max_block_df, max(12, int(n * 0.08)))

        for i, toks in enumerate(tokens_by_doc):
            scores: dict[int, float] = defaultdict(float)
            ranked_terms = sorted(set(toks), key=lambda t: df.get(t, n))
            for term in ranked_terms[:12]:
                idf = 1.0 / max(df.get(term, 1), 1)
                if df.get(term, n) > df_cap:
                    continue
                for j in postings[term]:
                    if j != i:
                        scores[j] += idf
            neighbors = sorted(scores, key=lambda j: (-scores[j], j))[:neighbor_k]
            for j in neighbors:
                add(i, j)

        # 5. Optional embedding retrieval (creates candidates only).
        if encoder is not None:
            vectors = [encoder.encode(t.input) for t in tests]
            from evaltrim.similarity import cosine

            for i, vec in enumerate(vectors):
                ranked: list[tuple[float, int]] = []
                for j, other in enumerate(vectors):
                    if j == i:
                        continue
                    ranked.append((cosine(vec, other), j))
                ranked.sort(key=lambda item: (-item[0], item[1]))
                for _, j in ranked[: min(12, self.neighbor_k)]:
                    add(i, j)

        return sorted(found)
