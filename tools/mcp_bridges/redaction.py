#!/usr/bin/env python3
"""ADR-0012 §2 extended tool-event scrubber — DasLab WS-A (ADR-0033 TB-3, C7).

The P3 tool-transcript scrubber ADR-0012 §2/§4 names. It removes the secret /
credential / PII classes from any Tier-B field (``reason``, ``output_summary``,
``args_digest`` shape) *before* it is length-capped and appended to an
append-only log — **redact, then truncate, then append** (ADR-0012 §2 mechanics),
**fail-closed** (an unclassifiable value drops to ``[REDACTED:unclassified]``,
never written raw).

This is the SECOND line of defence only. The PRIMARY control is structural: raw
tool payloads are Tier-F and never enter the store at all (ADR-0012 §1.4). This
regex set is best-effort — it does NOT claim completeness (ADR-0012 Consequences:
"the redaction set is best-effort, not perfect"). The high-entropy ``{32,}``
fallback is deliberately tuned to NOT over-redact legitimate Tier-M hash digests
(git SHAs, sha256, long numeric ids) per the ADR-0012 §215 tuning note.
"""
from __future__ import annotations

import re

# Order matters: specific, high-confidence patterns run BEFORE the greedy
# high-entropy fallback so a known secret gets its precise label (and cannot be
# half-eaten by the fallback). Each entry is (compiled_regex, replacement).
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Private-key PEM blocks — drop the whole block.
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:private_key]",
    ),
    # JWT — three base64url segments led by the standard ``eyJ`` header.
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
        "[REDACTED:jwt]",
    ),
    # Authorization: Bearer <token>  (also a bare "Bearer <token>").
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        "[REDACTED:bearer]",
    ),
    # Connection strings — scheme://user:pass@host. Credentials must be stripped;
    # we drop the whole DSN (host may leak otherwise-benign info but the safe
    # default is to redact the credential-bearing URL entirely).
    (
        re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]+@[^\s/]+", re.IGNORECASE),
        "[REDACTED:dsn]",
    ),
    # Anthropic API keys — sk-ant-<type><digits>-<long body>.
    (
        re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}"),
        "[REDACTED:api_key]",
    ),
    # AWS access key id.
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED:api_key]",
    ),
    # GitHub token family: ghp_ / gho_ / ghu_ / ghs_ / ghr_ + body.
    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "[REDACTED:api_key]",
    ),
    # PII — email addresses (run AFTER the DSN pattern so user:pass@host is gone).
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+\b"),
        "[REDACTED:pii]",
    ),
]

# PII — phone numbers. Conservative and LENGTH-BOUNDED (E.164 tops out ~15 digits):
# optional +, then 5-15 more chars of digits/separators, then a digit. The upper
# bound + word-boundary lookarounds stop it eating a long Tier-M numeric id (e.g. a
# 40-digit ledger id) — that neither fits the bound as a whole nor anchors partially.
_PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d ().\-]{5,15}\d(?![\w.])")

# High-entropy fallback: a long token that no specific pattern caught. Tuned NOT
# to redact Tier-M digests — a replacement callback skips pure-hex (git SHA /
# sha256), all-digit (ids), and all-alpha runs, so a 40-hex commit id or a 64-hex
# content digest survives while a random mixed-case/underscore/dash secret does not.
_HIGH_ENTROPY_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")
_HEX_RE = re.compile(r"[0-9a-fA-F]+")


def _high_entropy_sub(match: re.Match[str]) -> str:
    tok = match.group(0)
    core = tok.strip("_-")
    if not core:
        return tok
    if _HEX_RE.fullmatch(core):
        return tok  # Tier-M hash digest (git SHA / sha256) — do NOT redact
    if core.isdigit():
        return tok  # long numeric id — Tier-M
    if core.isalpha():
        return tok  # a long word, not a secret
    return "[REDACTED:secret]"


def scrub(text: str) -> str:
    """Redact every known secret / credential / PII class from *text*.

    Raises only if *text* is not string-coercible; callers that need the
    fail-closed guarantee use :func:`safe_scrub`.
    """
    if not isinstance(text, str):
        text = str(text)
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    out = _PHONE_RE.sub("[REDACTED:pii]", out)
    out = _HIGH_ENTROPY_RE.sub(_high_entropy_sub, out)
    return out


def safe_scrub(value: object) -> str:
    """Fail-closed scrub (ADR-0012 §2): any error drops the value, never leaks it."""
    try:
        return scrub(value if isinstance(value, str) else str(value))
    except Exception:  # noqa: BLE001 — a scrubber failure must never write raw content
        return "[REDACTED:unclassified]"


def redact_then_truncate(text: object, cap: int = 280) -> str:
    """ADR-0012 §2 ordering: scrub FIRST, then cap — a secret split by the cap
    cannot survive because it was already redacted before truncation."""
    scrubbed = safe_scrub(text)
    return scrubbed[:cap] if cap and cap > 0 else scrubbed


if __name__ == "__main__":  # pragma: no cover — manual probe
    import sys

    print(scrub(sys.stdin.read()))
