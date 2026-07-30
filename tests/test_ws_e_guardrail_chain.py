"""WS-E (DAS-1584) — Presidio + classifier + policy guardrail chain tests.

FR-006 (`docs/design/ws-e-tenant-hardening.md` §4.3): `tools/guardrails/chain.py`
must (a) detect + redact planted PII/secrets fail-closed, without
over-redacting Tier-M content; (b) deny an undeclared-role Presidio call via
the REUSED `audit_external_tool.decide()` — the same evaluator any other
external-tool call is judged by, not a chain-local one; (c) be byte-identical
inert when `ws_e_tenant_hardening` is OFF (the only state at merge).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chain = _load("tools/guardrails/chain.py", "ws_e_chain_under_test")
audit_hook = _load("tools/mcp_bridges/audit_external_tool.py", "ws_e_audit_hook_under_test")

_GRANTED = {"mcp__presidio__analyze_text": ["security-lead"]}


# --------------------------------------------------------------------------- #
# Flag-off ⇒ inert (byte-identical passthrough, no Presidio call, no decide())
# --------------------------------------------------------------------------- #

def test_flag_off_is_byte_identical_inert():
    text = "Contact Jane at jane.doe@example.com"
    result = chain.guard(text, role="frontend-eng-1", flag_override=False)
    assert result.output_text == text
    assert result.action == "inert-flag-off"
    assert result.denied is False
    assert result.entities == ()


def test_flag_off_never_consults_the_allowlist():
    """Even a role with NO grant at all must sail through unchanged when the
    flag is off — the allow-list is never even read (a `None`/empty allowlist
    proves `decide()` was never reached, since a granted role isn't required
    for the inert path to succeed)."""
    text = "some plain text"
    result = chain.guard(text, role="nobody", allowlist={}, flag_override=False)
    assert result.output_text == text
    assert result.action == "inert-flag-off"


# --------------------------------------------------------------------------- #
# Planted PII / secret is detected + redacted (fail-closed)
# --------------------------------------------------------------------------- #

def test_planted_email_pii_is_detected_and_redacted():
    text = "Contact Jane at jane.doe@example.com for the handoff."
    result = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.denied is False
    assert result.tier == "B"
    assert result.action == "redact"
    assert "EMAIL" in result.entities
    assert "jane.doe@example.com" not in result.output_text
    assert "[REDACTED:pii]" in result.output_text
    # Surrounding Tier-M-shaped context is preserved, not blanket-replaced.
    assert "Contact Jane at" in result.output_text
    assert "for the handoff." in result.output_text


def test_planted_secret_is_detected_and_redacted():
    fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"  # fragmented so it never sits whole in source
    text = f"rotate key {fake_key} now"
    result = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.denied is False
    assert result.tier == "B"
    assert result.action == "redact"
    assert "API_KEY" in result.entities
    assert fake_key not in result.output_text
    assert "[REDACTED:api_key]" in result.output_text


def test_planted_phone_pii_is_detected_and_redacted():
    text = "call the on-call at +1 415 555 0134 immediately"
    result = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.denied is False
    assert result.tier == "B"
    assert result.action == "redact"
    assert "+1 415 555 0134" not in result.output_text


# --------------------------------------------------------------------------- #
# No over-redaction of Tier-M content
# --------------------------------------------------------------------------- #

def test_clean_tier_m_content_passes_through_unchanged():
    text = "order 88421 status READY, hash a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    result = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.denied is False
    assert result.tier == "M"
    assert result.action == "allow"
    assert result.entities == ()
    assert result.output_text == text  # byte-identical — nothing was redacted


def test_git_sha_like_id_is_not_treated_as_a_secret():
    text = "build 5f2c1e9a7b3d4f0e8c1a2b3d4e5f60718293a4b5 passed CI"
    result = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.tier == "M"
    assert result.output_text == text


# --------------------------------------------------------------------------- #
# Undeclared-role call denied via the REUSED decide() — no side channel
# --------------------------------------------------------------------------- #

def test_undeclared_role_is_denied_and_presidio_never_runs():
    text = "Contact Jane at jane.doe@example.com"
    result = chain.guard(text, role="frontend-eng-1", allowlist=_GRANTED, flag_override=True)
    assert result.denied is True
    assert result.action == "deny"
    assert result.output_text is None  # Presidio never called — nothing leaked
    assert "not allow-listed" in result.reason


def test_denial_reason_matches_the_reused_decide_verbatim():
    """The chain's denial reason string is not a re-derived approximation —
    it is EXACTLY what `audit_external_tool.decide()` itself returns, proving
    the chain calls the real function rather than reimplementing the check."""
    expected_decision, expected_reason = audit_hook.decide(
        chain.PRESIDIO_TOOL_NAME, "frontend-eng-1", _GRANTED
    )
    assert expected_decision == "deny"
    result = chain.guard("hi", role="frontend-eng-1", allowlist=_GRANTED, flag_override=True)
    assert result.reason == expected_reason


def test_granted_role_is_allowed_through_the_same_decide():
    expected_decision, expected_reason = audit_hook.decide(
        chain.PRESIDIO_TOOL_NAME, "security-lead", _GRANTED
    )
    assert expected_decision == "allow"
    result = chain.guard("order 1 status READY", role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert result.denied is False
    assert result.reason == expected_reason


def test_empty_allowlist_denies_every_role_no_default_allow():
    result = chain.guard("hi", role="security-lead", allowlist={}, flag_override=True)
    assert result.denied is True
    assert result.action == "deny"


def test_wildcard_allowlist_value_is_rejected_not_honoured():
    """C2 — a malformed `"*"` roles value must never widen access, even if it
    somehow reached this module directly (bypassing `load_allowlist`'s own
    `_reject_wildcard` guard)."""
    result = chain.guard(
        "hi", role="anyone", allowlist={chain.PRESIDIO_TOOL_NAME: "*"}, flag_override=True
    )
    assert result.denied is True


# --------------------------------------------------------------------------- #
# classify_tier / policy_decide unit coverage
# --------------------------------------------------------------------------- #

def test_classify_tier_and_policy_decide_are_pure():
    assert chain.classify_tier(()) == "M"
    assert chain.classify_tier(("EMAIL",)) == "B"
    assert chain.policy_decide("M") == "allow"
    assert chain.policy_decide("B") == "redact"


# --------------------------------------------------------------------------- #
# Flag resolution — the features file is the only source
#
# This chain fails OPEN: with the flag resolved OFF it passes text through
# byte-identical, so redaction simply does not happen. An ambient value that
# could resolve it OFF was therefore able to strip redaction from a live
# guardrail without any caller asking for it. Two env doors existed —
# DASLAB_WS_E_FLAG (shared with the RBAC surface) and a DASLAB_FEATURES
# redirect that fully substituted for it — plus a Path.cwd() walk-up, so the
# flag a caller saw also depended on where the process started.
# --------------------------------------------------------------------------- #

def _features(tmp_path: Path, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_e_tenant_hardening: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def test_no_env_value_can_flip_the_chain_flag(tmp_path, monkeypatch):
    on = _features(tmp_path, on=True)
    off_dir = tmp_path / "off"
    off_dir.mkdir()
    off = _features(off_dir, on=False)
    for value in ("false", "0", "off", "", "true", "1"):
        monkeypatch.setenv("DASLAB_WS_E_FLAG", value)
        monkeypatch.setenv("DASLAB_FEATURES", str(off))
        assert chain.flag_on(features_path=on) is True, value
        monkeypatch.setenv("DASLAB_FEATURES", str(on))
        assert chain.flag_on(features_path=off) is False, value


def test_an_ambient_value_cannot_strip_redaction_from_a_live_chain(monkeypatch):
    """The concrete harm, asserted end-to-end rather than at the flag read: the
    committed config carries ws_e_tenant_hardening ON, so guard() with no
    flag_override must redact — and no ambient value may turn that into an
    inert passthrough that returns the PII intact."""
    text = "Contact jane@example.com now"
    for value in ("false", "0", "off"):
        monkeypatch.setenv("DASLAB_WS_E_FLAG", value)
        result = chain.guard(text, role="security-lead", allowlist=_GRANTED)
        assert result.action != "inert-flag-off", value
        assert "jane@example.com" not in (result.output_text or ""), value


def test_chain_flag_file_is_anchored_to_the_package_not_the_cwd(tmp_path, monkeypatch):
    assert chain.DEFAULT_FEATURES == ROOT / "config" / "features.yaml"
    monkeypatch.chdir(tmp_path)
    assert chain.flag_on() is chain.flag_on(features_path=ROOT / "config" / "features.yaml")


def test_explicit_flag_override_still_wins_for_callers_that_pass_one(tmp_path):
    """flag_override is the sanctioned caller-side seam (the golden-eval harness
    and the SC-005 composite use it); removing the env doors must not touch it."""
    text = "Contact jane@example.com now"
    inert = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=False)
    assert inert.output_text == text
    live = chain.guard(text, role="security-lead", allowlist=_GRANTED, flag_override=True)
    assert live.action != "inert-flag-off"
