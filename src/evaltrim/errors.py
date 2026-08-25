"""Typed errors with user-facing messages and exit codes."""

from __future__ import annotations


class EvalTrimError(Exception):
    """Base error. Exit code 1 unless overridden."""

    exit_code = 1


class SuiteValidationError(EvalTrimError):
    """The suite file is malformed or fails schema checks."""

    exit_code = 2


class SuiteNotFoundError(EvalTrimError):
    """The suite path does not exist."""

    exit_code = 2


class TestNotFoundError(EvalTrimError):
    """A requested test id is missing from the suite."""

    exit_code = 2


class StrictModeError(EvalTrimError):
    """Policy thresholds were violated in --strict mode."""

    exit_code = 3
