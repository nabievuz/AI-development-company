#!/usr/bin/env python3

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [

    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:private_key]",
    ),

    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
        "[REDACTED:jwt]",
    ),

    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        "[REDACTED:bearer]",
    ),


    (
        re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]+@[^\s/]+", re.IGNORECASE),
        "[REDACTED:dsn]",
    ),

    (
        re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
        "[REDACTED:api_key]",
    ),

    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+\b"),
        "[REDACTED:pii]",
    ),
]


_PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d ().\-]{5,15}\d(?![\w.])")


_HIGH_ENTROPY_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")
_HEX_RE = re.compile(r"[0-9a-fA-F]+")


def _high_entropy_sub(match: re.Match[str]) -> str:
    tok = match.group(0)
    core = tok.strip("_-")
    if not core:
        return tok
    if _HEX_RE.fullmatch(core):
        return tok
    if core.isdigit():
        return tok
    if core.isalpha():
        return tok
    return "[REDACTED:secret]"


def scrub(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    out = _PHONE_RE.sub("[REDACTED:pii]", out)
    out = _HIGH_ENTROPY_RE.sub(_high_entropy_sub, out)
    return out


def safe_scrub(value: object) -> str:
    try:
        return scrub(value if isinstance(value, str) else str(value))
    except Exception:
        return "[REDACTED:unclassified]"


def redact_then_truncate(text: object, cap: int = 280) -> str:
    scrubbed = safe_scrub(text)
    return scrubbed[:cap] if cap and cap > 0 else scrubbed


if __name__ == "__main__":
    import sys

    print(scrub(sys.stdin.read()))
