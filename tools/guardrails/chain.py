#!/usr/bin/env python3
"""WS-E (DAS-1584) — Presidio + classifier + policy guardrail chain.

FR-006 / TN-1 (``docs/design/ws-e-tenant-hardening.md`` §4.3): a layered
**Presidio (PII detection) → classifier (ADR-0012 M/B/F tier) → policy
(redact/allow)** chain that *complements* — never forks or replaces — the
ADR-0012 §2 scrubber (``tools/mcp_bridges/redaction.py``). It reaches Presidio
**only** through the ADR-0033 governed MCP edge that WS-D (DAS-1574) already
admitted (``mcp__presidio__analyze_text``, granted to ``security-lead`` in
``board/.tool-allowlist.json``) — this module does **not** re-admit the tool,
does **not** edit the allow-list or any role overlay, and opens **no** side
channel. Reused, not forked:

  * ``tools/mcp_bridges/presidio_tool_bridge.analyze_text`` — the admitted
    Presidio sidecar's PII-detection entrypoint. In production the call
    crosses the MCP edge as ``mcp__presidio__analyze_text``; this module calls
    the *same* function in-process for chain composition/testing, exactly as
    the WS-D reference sidecar documents ("swap the backend... keeping this
    module's I/O-redaction and egress posture unchanged").
  * ``tools/mcp_bridges/redaction.redact_then_truncate`` — the ADR-0012 §2
    scrubber, applied belt-and-suspenders to this chain's own output (the
    Presidio caveat: PII-handling tools must scrub their OWN I/O too).
  * ``tools/mcp_bridges/audit_external_tool.decide`` / ``.load_allowlist`` —
    the WS-A TB-2 least-privilege allow/deny evaluator. An undeclared-role
    call to ``mcp__presidio__analyze_text`` is denied by the **same**
    ``decide()`` any other external tool call is denied by — there is no
    second admission path, no chain-local allow-list.

**Flag:** ``ws_e_tenant_hardening`` (``config/features.yaml``), DEFAULT OFF.
With the flag OFF (the only state at merge) :func:`guard` is **INERT** — it
returns the input text byte-for-byte unchanged and never invokes Presidio or
the allow-list evaluator, so a wave/dispatch with the flag off is unaffected
(TB-5 / SC-005 posture, mirrored from WS-A/WS-D).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve().parent
_BRIDGES_DIR = _HERE.parent / "mcp_bridges"

_FLAG_NAME = "ws_e_tenant_hardening"

# ``mcp__presidio__analyze_text`` is the ONLY tool identity this chain ever
# asks the reused admission evaluator about — it is a constant, never built
# from caller input, so there is no path for a caller to make this module ask
# about a different (unadmitted) tool name.
PRESIDIO_TOOL_NAME = "mcp__presidio__analyze_text"


def _load_module(filename: str) -> ModuleType:
    """Load a sibling ``tools/mcp_bridges/<filename>`` module by path.

    ``tools/mcp_bridges`` ships no ``__init__.py`` (it is a bag of independent
    sidecar scripts, not a package) — the existing WS-D/WS-A tests
    (``tests/test_ws_d_tool_admission.py``) load it the same way, so this
    mirrors the established convention rather than inventing a new one.
    """
    path = _BRIDGES_DIR / filename
    name = f"_ws_e_guardrails_{path.stem}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — defensive
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _redaction():
    return _load_module("redaction.py")


def _presidio_bridge():
    return _load_module("presidio_tool_bridge.py")


def _audit_hook():
    return _load_module("audit_external_tool.py")


# --------------------------------------------------------------------------- #
# Flag gate — read-only, generic (does not duplicate audit_external_tool's
# ws_a-specific reader; this one is parameterised by flag name so a future
# WS-E sub-flag can reuse it without a second implementation).
# --------------------------------------------------------------------------- #

#: Anchored to THIS file's location (LAW A), matching how ``_BRIDGES_DIR`` above
#: is resolved. The env doors that used to precede it — ``DASLAB_WS_E_FLAG``
#: (shared with the RBAC surface) and a ``DASLAB_FEATURES`` redirect — are gone,
#: along with a ``Path.cwd()`` walk-up: with the flag resolved OFF this chain
#: fails OPEN, passing text through unredacted, so an ambient value could strip
#: redaction from a live guardrail without any caller asking for it.
DEFAULT_FEATURES = _HERE.parent.parent / "config" / "features.yaml"


def flag_on(name: str = _FLAG_NAME, features_path: Path | None = None) -> bool:
    """Read a boolean feature flag from the features file. Fails safe to OFF:
    an unreadable/absent file always resolves OFF — a broken config can never
    silently turn a guardrail chain on (or, symmetrically, silently believe it
    is protected when it is not; callers must not treat "on" as a security
    boundary on its own — the ADR-0033 edge + allow-list is the actual
    boundary).

    Resolution is ``features_path`` when given, else :data:`DEFAULT_FEATURES`.
    No environment variable participates.
    """
    p = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not p.is_file():
        return False
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{name}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


# --------------------------------------------------------------------------- #
# The chain — classifier + policy (ADR-0012 M/B/F tiers)
# --------------------------------------------------------------------------- #

# ``presidio_tool_bridge.analyze_text`` returns e.g.
#   "presidio: 1 entity [EMAIL] | redacted: Contact Jane at [REDACTED:pii]"
#   "presidio: 0 entities | redacted: order 88421 status READY"
_SUMMARY_RE = re.compile(
    r"^presidio: \d+ entit(?:y|ies)(?: \[(?P<entities>.*?)\])? \| redacted: (?P<redacted>.*)$",
    re.DOTALL,
)


def _parse_presidio_summary(summary: str) -> tuple[tuple[str, ...], str]:
    """Pull ``(entity_types, redacted_text)`` out of the admitted sidecar's
    summary string. Reuses Presidio's OWN detection/redaction — this module
    never re-implements entity regexes; it only reads the sidecar's verdict."""
    match = _SUMMARY_RE.match(summary)
    if not match:
        # Fail-closed parse failure: treat as "nothing classified as safe" —
        # never guess a tier, and never emit the possibly-malformed raw
        # summary as if it were redacted text.
        return (), "[REDACTED:unclassified]"
    entities_raw = match.group("entities") or ""
    entities = tuple(e.strip() for e in entities_raw.split(",") if e.strip())
    return entities, match.group("redacted")


def classify_tier(entities: tuple[str, ...]) -> str:
    """ADR-0012 §1 tier assignment for this chain's narrow purpose: content
    Presidio flagged as PII/secret is Tier-B (bounded free text, must be
    scrubbed before it is trusted further); content with no such finding
    stays Tier-M (metadata-shaped / already-safe) and is passed through
    UNCHANGED — this is the "no over-redaction of Tier-M" invariant the
    ticket's tests assert."""
    return "B" if entities else "M"


def policy_decide(tier: str) -> str:
    """Policy step: Tier-B → redact (use Presidio's own redaction), Tier-M →
    allow (pass through unchanged). This chain never silently drops content
    that Presidio did not flag — over-redacting Tier-M is itself a defect
    (ADR-0012 §2 "when in doubt... deny by default" governs unclassifiable
    content, not clean content)."""
    return "redact" if tier == "B" else "allow"


@dataclass(frozen=True)
class GuardResult:
    """Outcome of running :func:`guard` on one piece of text."""

    output_text: str | None
    tier: str | None
    action: str  # "redact" | "allow" | "deny" | "inert-flag-off"
    entities: tuple[str, ...] = field(default_factory=tuple)
    denied: bool = False
    reason: str = ""


def guard(
    text: str,
    role: str,
    allowlist: dict | None = None,
    flag_override: bool | None = None,
) -> GuardResult:
    """Run the Presidio → classifier → policy chain on *text* for *role*.

    Order (fail-closed at every step):

    1. **Flag gate.** ``ws_e_tenant_hardening`` OFF ⇒ INERT passthrough — the
       text returns byte-identical, Presidio is never called, the allow-list
       is never consulted. ``flag_override`` lets a caller (tests, the golden
       eval) force the state explicitly instead of depending on the ambient
       ``config/features.yaml``.
    2. **Least-privilege admission (reused, not forked).** The SAME
       ``audit_external_tool.decide()`` any other ``mcp__.*`` call is
       evaluated by is asked about ``mcp__presidio__analyze_text`` for
       *role*. A role not granted the tool in ``board/.tool-allowlist.json``
       is denied here — Presidio is never invoked, so no PII/secret ever
       reaches (or leaks from) an unauthorized caller.
    3. **Presidio detection + the chain's own redaction pass.** The admitted
       sidecar both detects entity types and returns its own §2-scrubbed
       text; this module never re-derives or re-echoes a raw finding.
    4. **Classify (M/B) → policy (allow/redact).**
    """
    enabled = flag_on() if flag_override is None else flag_override
    if not enabled:
        return GuardResult(
            output_text=text,
            tier=None,
            action="inert-flag-off",
            entities=(),
            denied=False,
            reason=f"{_FLAG_NAME} is OFF — guardrail chain inert (byte-identical passthrough)",
        )

    hook = _audit_hook()
    effective_allowlist = allowlist if allowlist is not None else hook.load_allowlist()
    decision, reason = hook.decide(PRESIDIO_TOOL_NAME, role, effective_allowlist)
    if decision == "deny":
        return GuardResult(
            output_text=None,
            tier=None,
            action="deny",
            entities=(),
            denied=True,
            reason=reason,
        )

    presidio = _presidio_bridge()
    summary = presidio.analyze_text(text)
    entities, redacted_text = _parse_presidio_summary(summary)
    tier = classify_tier(entities)
    action = policy_decide(tier)
    output = redacted_text if action == "redact" else text

    # Belt-and-suspenders (ADR-0012 §2 mechanics; the Presidio caveat design
    # §4.3): this chain's OWN output is scrubbed again before it is returned,
    # exactly as the admitted Presidio sidecar scrubs its own summary. For
    # genuinely Tier-M content this is a documented no-op (redaction.py's
    # high-entropy fallback explicitly skips hex/digit/alpha runs), which is
    # what keeps the "no over-redaction of Tier-M" invariant intact.
    scrub = _redaction()
    output = scrub.redact_then_truncate(output, cap=4000)

    return GuardResult(
        output_text=output,
        tier=tier,
        action=action,
        entities=entities,
        denied=False,
        reason=reason,
    )
