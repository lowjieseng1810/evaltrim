"""Versioned machine-readable JSON contract."""

from __future__ import annotations

import json
from typing import Any

from evaltrim.constants import CONTRACT_VERSION


def envelope(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.setdefault("contract_version", CONTRACT_VERSION)
    body.setdefault("command", command)
    return body


def dumps(command: str, payload: dict[str, Any]) -> str:
    return json.dumps(envelope(command, payload), indent=2, default=str)
