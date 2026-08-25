"""EvalTrim: prove which AI-agent tests are worth keeping."""

from evaltrim.models import (
    AnalysisResult,
    Behavior,
    CoverageResult,
    MaintenanceReport,
    Recommendation,
    RemovalSimulation,
    RunStats,
    SuiteSummary,
    TestCase,
    TestEvidence,
    TestSuite,
)

__version__ = "0.7.0"
__all__ = [
    "AnalysisResult",
    "Behavior",
    "CoverageResult",
    "MaintenanceReport",
    "Recommendation",
    "RemovalSimulation",
    "RunStats",
    "SuiteSummary",
    "TestCase",
    "TestEvidence",
    "TestSuite",
    "__version__",
]
