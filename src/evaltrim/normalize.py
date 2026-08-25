"""Deterministic text normalization for paraphrase-aware lexical similarity."""

from __future__ import annotations

import re

# Common English number words used in agent evals (deterministic, finite).
_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

SYNONYMS: dict[str, str] = {
    "return": "refund",
    "returning": "refund",
    "returned": "refund",
    "reimburse": "refund",
    "reimbursement": "refund",
    "chargeback": "refund",
    "please": "",
    "could": "",
    "would": "",
    "want": "",
    "need": "",
    "get": "",
    "give": "",
    "dollars": "",
    "dollar": "",
    "usd": "",
    "can": "",
    "you": "",
    "me": "",
    "my": "",
    "i": "",
    "a": "",
    "an": "",
    "the": "",
    "of": "",
    "to": "",
    "for": "",
    "and": "",
}

_TOKEN_RE = re.compile(r"[a-z0-9_$]+")
_MONEY_RE = re.compile(r"\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)")


def word_to_number(tokens: list[str]) -> list[str]:
    """Replace simple number-word sequences with digits (e.g. six hundred -> 600)."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in _ONES or t in _TENS:
            value = _ONES.get(t, _TENS.get(t, 0))
            j = i + 1
            if j < len(tokens) and tokens[j] == "hundred":
                value *= 100
                j += 1
                if j < len(tokens) and (tokens[j] in _ONES or tokens[j] in _TENS):
                    value += _ONES.get(tokens[j], _TENS.get(tokens[j], 0))
                    j += 1
            elif j < len(tokens) and tokens[j] in _ONES and t in _TENS:
                value += _ONES[tokens[j]]
                j += 1
            if j < len(tokens) and tokens[j] in {"dollar", "dollars"}:
                j += 1
            out.append(str(value))
            i = j
            continue
        out.append(t)
        i += 1
    return out


def normalize_text(text: str) -> str:
    lowered = text.lower().replace(",", "")
    tokens = _TOKEN_RE.findall(lowered)
    tokens = word_to_number(tokens)
    normalized: list[str] = []
    for tok in tokens:
        if tok.startswith("$"):
            tok = tok[1:]
        mapped = SYNONYMS.get(tok, tok)
        if mapped == "":
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", mapped):
            normalized.append(f"amt_{mapped.split('.')[0]}")
        else:
            normalized.append(mapped)
    return " ".join(normalized)


def char_ngrams(text: str, n: int = 3) -> list[str]:
    compact = re.sub(r"\s+", " ", normalize_text(text)).strip()
    if len(compact) < n:
        return [compact] if compact else []
    padded = f" {compact} "
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


def extract_amounts(text: str) -> list[float]:
    values: list[float] = []
    for match in _MONEY_RE.findall(text.replace(",", "")):
        try:
            values.append(float(match))
        except ValueError:
            continue
    # Also recover amt_N from normalized form.
    for tok in normalize_text(text).split():
        if tok.startswith("amt_"):
            try:
                values.append(float(tok[4:]))
            except ValueError:
                continue
    # Dedupe preserving order.
    seen: set[float] = set()
    out: list[float] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
