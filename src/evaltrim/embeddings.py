"""Optional local semantic encodings. Default path never calls a network."""

from __future__ import annotations

import hashlib
import json
import math
import os
from abc import ABC, abstractmethod
from pathlib import Path

from evaltrim.normalize import char_ngrams, normalize_text
from evaltrim.similarity import cosine


def cache_dir() -> Path:
    override = os.environ.get("EVALTRIM_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "evaltrim"


class SemanticEncoder(ABC):
    """Maps text to a sparse or dense vector. Implementations must be local by default."""

    name = "base"

    @abstractmethod
    def encode(self, text: str) -> dict[str, float]:
        raise NotImplementedError

    def similarity(self, left: str, right: str) -> float:
        return cosine(self.encode(left), self.encode(right))


class HashingNgramEncoder(SemanticEncoder):
    """Lightweight local hashing encoder (char 3-grams). No extra packages."""

    name = "hashing_ngram"

    def __init__(self, dims: int = 256) -> None:
        self.dims = dims

    def encode(self, text: str) -> dict[str, float]:
        grams = char_ngrams(text, 3)
        if not grams:
            grams = normalize_text(text).split() or ["_empty"]
        vec = [0.0] * self.dims
        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return {str(i): v / norm for i, v in enumerate(vec) if v != 0.0}


class CachedEncoder(SemanticEncoder):
    """Content-hash cache around another encoder. Disk optional."""

    def __init__(self, inner: SemanticEncoder, *, persist: bool = False) -> None:
        self.inner = inner
        self.name = f"cached:{inner.name}"
        self.persist = persist
        self.memory: dict[str, dict[str, float]] = {}
        self._dir = cache_dir() / "embeddings"
        if persist:
            self._dir.mkdir(parents=True, exist_ok=True)

    def encode(self, text: str) -> dict[str, float]:
        key = hashlib.sha256(f"{self.inner.name}\n{text}".encode()).hexdigest()
        if key in self.memory:
            return self.memory[key]
        path = self._dir / f"{key}.json"
        if self.persist and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.memory[key] = data
            return data
        vec = self.inner.encode(text)
        self.memory[key] = vec
        if self.persist:
            path.write_text(json.dumps(vec), encoding="utf-8")
        return vec


def load_encoder(*, enabled: bool = False, persist: bool = False) -> SemanticEncoder | None:
    """Return a local encoder when embeddings are opted in; otherwise None.

    No third-party model is downloaded. The hashing encoder is optional layer 3.
    """
    if not enabled and os.environ.get("EVALTRIM_EMBEDDINGS", "").lower() not in {"1", "true", "yes"}:
        return None
    return CachedEncoder(HashingNgramEncoder(), persist=persist)
