"""Optional LLM adapters. Defaults never send data off-box."""

from __future__ import annotations

from abc import ABC, abstractmethod

from evaltrim.models import Behavior, TestCase


class BehaviorExtractor(ABC):
    @abstractmethod
    def extract(self, test: TestCase) -> Behavior | None:
        raise NotImplementedError


class SemanticComparator(ABC):
    @abstractmethod
    def similarity(self, left: str, right: str) -> float:
        raise NotImplementedError


class OracleAnalyzer(ABC):
    @abstractmethod
    def conflict_score(self, expected_a: str, expected_b: str) -> float:
        raise NotImplementedError


class NullBehaviorExtractor(BehaviorExtractor):
    def extract(self, test: TestCase) -> Behavior | None:
        return None


class DisabledLLM:
    """Placeholder used when EVALTRIM_LLM_PROVIDER is unset."""

    enabled = False
