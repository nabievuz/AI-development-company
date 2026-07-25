"""WS-A tool-bridge tests (ADR-0033 / DAS-1547).

Positive + negative unit coverage for the GATE-2 security conditions C1–C7,
plus the DAS-1549 (AADL Stage-4 / GATE-4) formal adversarial negative-test
suite bound by the CTO at GATE-2 closure — T1–T5 and SC-001/SC-002/SC-003.
MCP-dependent parts skip if ``mcp`` is absent (the sidecar is optional infra —
absent ⇒ the tool does not exist).

  C1  board/.tool-allowlist.json is a tracked generate-and-diff artifact
  C2  the compiler never emits a "*" roles value; decide()/load reject one
  C3  the PreToolUse hook fails CLOSED (binding present; spawn/crash → deny)
  C4  egress disables redirect-following
  C5  egress resolves the target and blocks internal ranges (SSRF)
  C6  domain matching anchors on a label boundary
  C7  the ADR-0012 §2 extended scrubber redacts, ordered redact-then-truncate,
      without over-redacting Tier-M digests

DAS-1549 negative-test suite (mcp_bridges layer; see test_ws_a_browser_tool_
egress.py for the browser-layer T2/T3):

  SC-001  a globally-granted/no-overlay tool is refused; a call that skips
          the PreToolUse audit write is still denied
  SC-002  egress block to a non-allow-listed domain; a tool-EVENT redaction
          probe (not just a raw string) passes end to end (ADR-0012)
  SC-003  flag-OFF ⇒ dispatch is byte-identical to pre-merge (no-op, no audit)
  T1 (C3) a hook-exec crash ⇒ DENIED fail-closed, INCLUDING the red-team
          residual: flag-ON + an unparseable/malformed event ⇒ deny
  T2 (C4) an allow-listed host that 302s to a non-allow-listed host is
          denied and the redirect target is never fetched (real HTTP hop)
  T3 (C5) resolve-time SSRF block holds under a DNS-rebinding-style resolver
  T4 (C2) a "*" roles value never grants any-role (see C2 tests above)
  T5 (C1) the drift guard detects a tampered/stale compiled allow-list
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BRIDGES = ROOT / "tools" / "mcp_bridges"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_gen_subagents():
    sys.path.insert(0, str(ROOT / "scripts"))
    import gen_subagents  # noqa: PLC0415

    return gen_subagents


hook = _load("tools/mcp_bridges/audit_external_tool.py", "audit_external_tool")
bridge = _load("tools/mcp_bridges/langchain_tool_bridge.py", "langchain_tool_bridge")
egress = _load("tools/mcp_bridges/egress_guard.py", "egress_guard")
redaction = _load("tools/mcp_bridges/redaction.py", "redaction")


# --------------------------------------------------------------------------- #
# TB-2 base allow/deny (unchanged behaviour, kept green)
# --------------------------------------------------------------------------- #

def test_denies_unlisted_external_tool():
    assert hook.decide("mcp__playwright__browser_navigate", "engineer-ic", {})[0] == "deny"


def test_allows_listed_role_only():
    allow = {"mcp__playwright": ["qa-lead", "design-ic"]}
    assert hook.decide("mcp__playwright__browser_navigate", "qa-lead", allow)[0] == "allow"
    assert hook.decide("mcp__playwright__browser_navigate", "engineer-ic", allow)[0] == "deny"


def test_non_external_tools_pass_through():
    assert hook.decide("Read", "engineer-ic", {})[0] == "allow"


def test_server_of_parsing():
    assert hook.server_of("mcp__playwright__browser_click") == "mcp__playwright"


# --------------------------------------------------------------------------- #
# C1 — tracked generate-and-diff allow-list
# --------------------------------------------------------------------------- #

def test_c1_tool_allowlist_is_tracked():
    """The compiled allow-list is a real committed file (not gitignored)."""
    path = ROOT / "board" / ".tool-allowlist.json"
    assert path.is_file(), "board/.tool-allowlist.json must exist as a tracked baseline"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=ROOT
    )
    assert ignored.returncode != 0, "board/.tool-allowlist.json must NOT be gitignored (C1)"


def test_c1_allowlist_matches_overlays_no_drift():
    """Generate-and-diff: the committed JSON equals a fresh compile of the overlays.

    A hand-edit of the JSON, or an overlay grant added without re-running the
    generator, diverges here → a red build (C1 mechanism that actually works).
    """
    gen = _load_gen_subagents()
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    regenerated = gen.compile_tool_allowlist()
    assert committed == regenerated


# --------------------------------------------------------------------------- #
# C2 — no "*" roles value, ever
# --------------------------------------------------------------------------- #

def test_c2_server_wide_grant_compiles_to_explicit_roles():
    """A ``tools: ["*"]`` overlay grant compiles to an EXPLICIT role list, not "*"."""
    gen = _load_gen_subagents()
    overlay = """## External tools
```yaml
external_tools:
  - server: mcp__playwright
    tools: ["*"]
    egress_profile: research-read
    reason: server-wide grant test
```
"""
    compiled = gen.compile_tool_allowlist([("qa-lead", overlay)])
    assert compiled == {"mcp__playwright": ["qa-lead"]}
    # C2 invariant: no value anywhere is the literal "*".
    for value in compiled.values():
        assert value != "*"
        assert "*" not in value


def test_c2_tool_level_grant_compiles():
    gen = _load_gen_subagents()
    overlay = """## External tools
```yaml
external_tools:
  - server: mcp__langchain-tools
    tools: ["web_fetch"]
    egress_profile: research-read
    reason: sourced research
```
"""
    compiled = gen.compile_tool_allowlist([("product-analyst", overlay)])
    assert compiled == {"mcp__langchain-tools__web_fetch": ["product-analyst"]}


def test_c2_decide_denies_wildcard_roles_value():
    """decide() never treats a "*" roles value as any-role (both str and in-list)."""
    assert hook.decide("mcp__x__t", "anyone", {"mcp__x": "*"})[0] == "deny"
    assert hook.decide("mcp__x__t", "anyone", {"mcp__x": ["*"]})[0] == "deny"
    assert hook.decide("mcp__x__t", "*", {"mcp__x": ["*"]})[0] == "deny"


def test_c2_load_allowlist_rejects_wildcard(tmp_path, monkeypatch):
    """A compiled map containing any "*" value is treated as deny-all at load."""
    p = tmp_path / "al.json"
    p.write_text(json.dumps({"mcp__x": "*"}))
    monkeypatch.setenv("DASLAB_TOOL_ALLOWLIST", str(p))
    assert hook.load_allowlist() == {}
    p.write_text(json.dumps({"mcp__x": ["*"]}))
    assert hook.load_allowlist() == {}
    # a clean list survives
    p.write_text(json.dumps({"mcp__x": ["qa-lead"]}))
    assert hook.load_allowlist() == {"mcp__x": ["qa-lead"]}


# --------------------------------------------------------------------------- #
# C3 — PreToolUse hook fails CLOSED + binding present + flag-off inert
# --------------------------------------------------------------------------- #

def test_c3_settings_binding_present_and_failclosed():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    pre = settings["hooks"]["PreToolUse"]
    entry = next(e for e in pre if e.get("matcher") == "mcp__.*")
    cmd = entry["hooks"][0]["command"]
    assert "audit_external_tool.py" in cmd
    assert "exit 2" in cmd, "the wrapper must fail CLOSED on hook-exec failure (C3)"


def test_c3_decode_failclosed():
    # malformed/empty event → deny for any external tool (via empty allowlist)
    assert hook.decide("mcp__x__t", "unknown", {})[0] == "deny"
    # non-list entry (e.g. corrupt map) → deny
    assert hook.decide("mcp__x__t", "unknown", {"mcp__x": "qa-lead"})[0] == "deny"


def test_infra_mcp_servers_are_never_governed():
    """ArcRift/obsidian (core memory/plumbing) are internal infrastructure — the
    WS-A allow-list governs ecosystem bridges only. They are allowed even with an
    empty allow-list AND an unknown identity, so flipping the flag never denies a
    role's (or the operator's) mandatory Persistent Memory Law ArcRift call."""
    for tool in ("mcp__ArcRift__store_memory", "mcp__ArcRift__recall_context", "mcp__obsidian__anything"):
        assert hook.decide(tool, "unknown", {})[0] == "allow", tool
        assert hook.decide(tool, "backend-em", {})[0] == "allow", tool
    # A NON-infra ecosystem tool stays fail-closed (deny) when ungranted.
    assert hook.decide("mcp__playwright__browser_navigate", "unknown", {})[0] == "deny"


def test_infra_mcp_carveout_is_env_overridable(monkeypatch):
    """DASLAB_INFRA_MCP scopes the carve-out; a server outside it stays governed."""
    monkeypatch.setenv("DASLAB_INFRA_MCP", "mcp__ArcRift")
    assert hook.decide("mcp__ArcRift__x", "unknown", {})[0] == "allow"
    assert hook.decide("mcp__obsidian__x", "unknown", {})[0] == "deny"  # no longer exempt


def _run_hook(event: dict, env_extra: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(BRIDGES / "audit_external_tool.py")],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def test_c3_flag_off_is_inert(tmp_path):
    """Flag OFF ⇒ every call passes through (allow), and no audit line is written
    (byte-identical to pre-merge — ArcRift/obsidian are never denied)."""
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        {"tool_name": "mcp__ArcRift__store_memory", "agent": "backend-em"},
        {"DASLAB_WS_A_FLAG": "off", "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
    )
    assert r.returncode == 0
    assert json.loads(r.stdout) == {}  # allow
    assert not audit_log.exists()  # inert: no side effect


def test_c3_flag_on_enforces_and_audits(tmp_path):
    """Flag ON + empty allow-list ⇒ deny, and the decision is audited (scrubbed)."""
    audit_log = tmp_path / "audit.jsonl"
    empty_allow = tmp_path / "al.json"
    empty_allow.write_text("{}")
    r = _run_hook(
        {"tool_name": "mcp__playwright__browser_navigate", "agent": "backend-em"},
        {
            "DASLAB_WS_A_FLAG": "on",
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(empty_allow),
        },
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert audit_log.exists()
    rec = json.loads(audit_log.read_text().splitlines()[-1])
    assert rec["decision"] == "deny"


def test_c3_wrapper_denies_on_spawn_failure():
    """The shell wrapper form fails CLOSED (exit 2) if the interpreter cannot run."""
    r = subprocess.run(
        ["sh", "-c", "python3 /nonexistent/definitely_missing.py || exit 2"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2


# --------------------------------------------------------------------------- #
# C4 — no redirect following
# --------------------------------------------------------------------------- #

def test_c4_no_redirect_handler_refuses():
    h = bridge._NoRedirect()
    # redirect_request returning None makes urllib NOT follow the 3xx.
    assert h.redirect_request(None, None, 302, "Found", {}, "http://evil.internal/") is None


def test_c4_web_fetch_egress_gate_before_network(monkeypatch):
    """With no egress profile (deny-all default), web_fetch refuses BEFORE any
    network call — so a redirect can never even be reached."""
    monkeypatch.delenv("DASLAB_EGRESS_PROFILE", raising=False)
    out = bridge.web_fetch("https://evil.example/steal")
    assert out.startswith("error:")
    assert "egress denied" in out


def test_web_fetch_rejects_non_url():
    assert bridge.web_fetch("not-a-url").startswith("error:")


# --------------------------------------------------------------------------- #
# C5 — resolve + block internal ranges (SSRF)
# --------------------------------------------------------------------------- #

def _resolver_returning(*ips):
    return lambda host, port: [(None, None, None, None, (ip, 0)) for ip in ips]


PROFILES = {"research-read": ["api.crossref.org", "*.wikipedia.org"], "none": []}


def test_c5_blocks_loopback_linklocal_rfc1918():
    for bad in ("127.0.0.1", "169.254.169.254", "10.0.0.5", "192.168.1.1", "172.16.0.9"):
        allowed, reason = egress.check_egress(
            "https://api.crossref.org/works",
            "research-read",
            PROFILES,
            resolver=_resolver_returning(bad),
        )
        assert not allowed, f"{bad} must be blocked"
        assert "internal" in reason


def test_c5_allows_public_resolved_host():
    allowed, _ = egress.check_egress(
        "https://api.crossref.org/works",
        "research-read",
        PROFILES,
        resolver=_resolver_returning("104.16.0.1"),
    )
    assert allowed


def test_c5_deny_by_default_empty_or_absent_profile():
    pub = _resolver_returning("104.16.0.1")
    assert not egress.check_egress("https://api.crossref.org/", "none", PROFILES, pub)[0]
    assert not egress.check_egress("https://api.crossref.org/", "missing", PROFILES, pub)[0]
    assert not egress.check_egress("https://api.crossref.org/", None, {}, pub)[0]


def test_c5_unresolvable_host_denied():
    allowed, reason = egress.check_egress(
        "https://api.crossref.org/",
        "research-read",
        PROFILES,
        resolver=_resolver_returning(),  # resolves to nothing
    )
    assert not allowed
    assert "did not resolve" in reason


# --------------------------------------------------------------------------- #
# C6 — label-boundary domain matching
# --------------------------------------------------------------------------- #

def test_c6_plain_entry_label_boundary():
    assert egress.host_matches("example.org", ["example.org"])
    assert egress.host_matches("api.example.org", ["example.org"])
    assert not egress.host_matches("evilexample.org", ["example.org"])
    assert not egress.host_matches("example.org.evil.com", ["example.org"])
    assert not egress.host_matches("notexample.org", ["example.org"])


def test_c6_wildcard_entry_subdomains_only():
    assert egress.host_matches("en.wikipedia.org", ["*.wikipedia.org"])
    assert not egress.host_matches("wikipedia.org", ["*.wikipedia.org"])  # apex excluded
    assert not egress.host_matches("evilwikipedia.org", ["*.wikipedia.org"])


def test_c6_full_check_rejects_lookalike_suffix():
    pub = _resolver_returning("104.16.0.1")
    assert not egress.check_egress("https://evilwikipedia.org/", "research-read", PROFILES, pub)[0]
    assert egress.check_egress("https://en.wikipedia.org/", "research-read", PROFILES, pub)[0]


# --------------------------------------------------------------------------- #
# C7 — ADR-0012 §2 extended scrubber
# --------------------------------------------------------------------------- #

def test_c7_redacts_all_classes():
    samples = {
        "sk-ant-api03-" + "A" * 50: "[REDACTED:api_key]",
        "AKIA" + "1234567890ABCDEF": "[REDACTED:api_key]",
        "ghp_" + "b" * 36: "[REDACTED:api_key]",
        "Authorization: Bearer " + "c" * 40: "[REDACTED:bearer]",
        "eyJhbGciOi.eyJzdWIiOm.SflKxwRJSM": "[REDACTED:jwt]",
        "postgres://user:pass@db.internal:5432/app": "[REDACTED:dsn]",
        "contact me at alice@example.com now": "[REDACTED:pii]",
    }
    for raw, token in samples.items():
        scrubbed = redaction.scrub(raw)
        assert token in scrubbed, f"{raw!r} → {scrubbed!r}"

    # Assemble the PEM markers at runtime so no contiguous secret-shaped literal
    # sits in the source tree (keeps the CI secret-scanner green on this fixture).
    marker = "PRIVATE KEY"
    pem = f"-----BEGIN RSA {marker}-----\nMIIabc\n-----END RSA {marker}-----"
    assert redaction.scrub(pem) == "[REDACTED:private_key]"


def test_c7_no_raw_secret_substring_survives():
    secret = "sk-ant-api03-" + "Zz9" * 20
    scrubbed = redaction.scrub(f"key is {secret} ok")
    assert secret not in scrubbed
    assert "[REDACTED:api_key]" in scrubbed


def test_c7_no_over_redaction_of_tier_m_digests():
    """A git SHA / sha256 / long numeric id is Tier-M and must survive intact."""
    git_sha = "e0f3215abc9912ef0011223344556677889900aa"  # 40 hex
    sha256 = "a" * 64  # 64 hex
    numeric_id = "1234567890" * 4  # 40 digits
    for digest in (git_sha, sha256, numeric_id):
        assert redaction.scrub(f"digest {digest} end") == f"digest {digest} end"


def test_c7_high_entropy_fallback_catches_mixed_secret():
    tok = "aB3" + "xY7_" * 10  # 43 chars mixed case + digits + underscore, not hex
    assert "[REDACTED:secret]" in redaction.scrub(f"token={tok}")


def test_c7_redact_then_truncate_ordering():
    secret = "sk-ant-api03-" + "Q" * 60
    # Cap lands in the middle of where the raw secret was; because we scrub FIRST,
    # no partial secret can survive the truncation.
    out = redaction.redact_then_truncate(f"leading {secret} trailing", cap=25)
    assert "sk-ant" not in out
    assert len(out) <= 25


def test_c7_safe_scrub_fail_closed(monkeypatch):
    monkeypatch.setattr(redaction, "scrub", lambda _t: (_ for _ in ()).throw(RuntimeError("boom")))
    assert redaction.safe_scrub("anything") == "[REDACTED:unclassified]"


# --------------------------------------------------------------------------- #
# DAS-1549 — SC-001: globally-granted/no-overlay tool refused; audit-skip
# (audit-write failure) does not widen a decision to allow
# --------------------------------------------------------------------------- #

def test_sc001_no_overlay_entry_refused():
    """A tool with NO overlay allow-list entry at all (not a global/wildcard
    grant, not present in the compiled map) is refused — TB-2 no default-allow."""
    assert hook.decide("mcp__globaltool__anything", "engineer-ic", {})[0] == "deny"


def test_sc001_audit_write_failure_still_denies(monkeypatch):
    """A call whose audit record CANNOT be written (e.g. the log path is
    unwritable — the ``PreToolUse`` audit step effectively 'skipped') must
    still be DENIED: the audit() failure is swallowed (never blocks a wave)
    but must never flip an already-computed deny into an allow."""
    decision, _reason = hook.decide("mcp__playwright__browser_navigate", "engineer-ic", {})
    assert decision == "deny"
    # audit() itself fails closed-silent (OSError swallowed) without touching
    # the decision that was already made.
    hook.audit({"ts": "t", "tool": "x", "agent": "y", "decision": decision, "reason": "r"})
    monkeypatch.setenv("DASLAB_TOOL_AUDIT_LOG", "/nonexistent-dir-xyz/does/not/exist/audit.jsonl")
    hook.audit({"ts": "t", "tool": "x", "agent": "y", "decision": decision, "reason": "r"})
    assert decision == "deny"  # unchanged — audit is a side effect, not a gate


# --------------------------------------------------------------------------- #
# DAS-1549 — SC-002: egress block (see C5/C6 above) + a tool-EVENT redaction
# probe proven end to end through audit(), not just the scrubber in isolation
# --------------------------------------------------------------------------- #

def test_sc002_tool_event_redaction_probe(tmp_path, monkeypatch):
    """Simulate a decide() reason that embeds a secret-shaped token (as it
    would if a leaked credential ever ended up in an agent identifier used
    inside a deny reason) and prove the exact ``main()`` write path —
    ``audit()`` fed a ``redact_then_truncate``-scrubbed ``reason`` — never
    persists the raw secret in that field. This exercises the AUDIT
    INTEGRATION point (main()'s own call to the scrubber), not just the
    standalone scrubber already covered by the C7 tests above. (The
    ``tool``/``agent`` identifier fields are structured role/tool KEYS, not
    free-text Tier-B content, so ADR-0012 scoping does not require them to
    be scrubbed — only ``reason``, which is where free text can appear, is
    in scope here.)"""
    leaked = "sk-ant-api03-" + "Q" * 50
    tool_name = "mcp__x__t"
    decision, reason = hook.decide(tool_name, leaked, {"mcp__x__t": ["qa-lead"]})
    assert decision == "deny"
    assert leaked in reason  # the raw (pre-scrub) reason DOES contain it

    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("DASLAB_TOOL_AUDIT_LOG", str(audit_log))
    from redaction import redact_then_truncate as _scrub  # same import main() uses

    hook.audit(
        {
            "ts": "t",
            "tool": tool_name,
            "agent": "engineer-ic",
            "decision": decision,
            "reason": _scrub(reason, 280),
        }
    )
    persisted = json.loads(audit_log.read_text().splitlines()[-1])
    assert leaked not in persisted["reason"], "raw secret must never survive in the audit reason (ADR-0012)"
    assert "[REDACTED" in persisted["reason"]


# --------------------------------------------------------------------------- #
# DAS-1549 — SC-003: flag-OFF is a byte-identical no-op, no audit write, even
# for a tool that WOULD be denied if the flag were on
# --------------------------------------------------------------------------- #

def test_sc003_flag_off_no_op_even_for_a_would_be_denied_tool(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        {"tool_name": "mcp__playwright__browser_navigate", "agent": "engineer-ic"},
        {"DASLAB_WS_A_FLAG": "off", "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
    )
    assert r.returncode == 0
    assert json.loads(r.stdout) == {}  # allow — byte-identical to pre-merge
    assert not audit_log.exists()  # no side effect at all


# --------------------------------------------------------------------------- #
# DAS-1549 — T1 (C3): hook-exec CRASH ⇒ fail-closed deny (exit 2), including
# the red-team residual — flag-ON + an unparseable/malformed event
# --------------------------------------------------------------------------- #

def test_t1_internal_crash_denies_and_exits_2():
    """Mirrors the EXACT ``if __name__ == "__main__":`` fail-closed wrapper in
    audit_external_tool.py (an internal exception during ``main()`` is caught,
    emits a deny, and exits 2) by forcing ``decide()`` to raise, proving the
    documented fail-closed contract holds for a genuine internal crash — not
    just a spawn failure (already covered by test_c3_wrapper_denies_on_spawn_
    failure)."""
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(BRIDGES)!r})
        import audit_external_tool as hook
        hook.decide = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            raise SystemExit(hook.main())
        except SystemExit:
            raise
        except Exception as exc:
            hook._emit_deny(f"hook internal error — fail-closed deny ({{type(exc).__name__}})")
            raise SystemExit(2) from exc
        """
    )
    env = dict(os.environ)
    env.update({"DASLAB_WS_A_FLAG": "on", "DASLAB_TOOL_ALLOWLIST": "/tmp/does-not-exist.json"})
    r = subprocess.run(
        [sys.executable, "-c", script],
        input='{"tool_name":"mcp__x__t","agent":"a"}',
        text=True,
        capture_output=True,
        env=env,
    )
    assert r.returncode == 2, "an internal crash MUST fail CLOSED (exit 2), never fail open"
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_t1_malformed_event_with_flag_on_must_deny_not_allow(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    empty_allow = tmp_path / "al.json"
    empty_allow.write_text("{}")
    env = dict(os.environ)
    env.update(
        {
            "DASLAB_WS_A_FLAG": "on",
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(empty_allow),
        }
    )
    r = subprocess.run(
        [sys.executable, str(BRIDGES / "audit_external_tool.py")],
        input="{not valid json",  # malformed stdin event, flag ON
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )
    out = json.loads(r.stdout)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", (
        "a malformed event with the flag ON must DENY, not silently allow "
        "(DAS-1547 red-team residual, upgraded to MUST-PASS by the CTO)"
    )


# --------------------------------------------------------------------------- #
# DAS-1549 — T2 (C4): allow-listed host 302s to a non-allow-listed host ⇒
# denied, and the redirect target is NEVER fetched (real HTTP round-trip,
# not just the unit-level _NoRedirect/gate-ordering checks above)
# --------------------------------------------------------------------------- #

class _RedirectingHandler(http.server.BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self):  # noqa: N802
        type(self).hits.append(self.path)
        self.send_response(302)
        self.send_header("Location", "http://internal-target.example.invalid/secret")
        self.end_headers()

    def log_message(self, *_a):  # silence test noise
        pass


def test_t2_allowlisted_host_redirect_to_disallowed_host_is_denied_and_never_fetched(
    monkeypatch,
):
    _RedirectingHandler.hits = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _RedirectingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as prof:
            yaml.safe_dump({"profiles": {"loopback-test": ["127.0.0.1"]}}, prof)
        monkeypatch.setenv("DASLAB_EGRESS_ALLOWLIST", prof.name)
        monkeypatch.setenv("DASLAB_EGRESS_PROFILE", "loopback-test")

        out = bridge.web_fetch(f"http://127.0.0.1:{port}/")

        assert out.startswith("error:")
        # Only the ORIGIN was ever hit — the redirect (to a wholly different,
        # non-allow-listed host) was refused before urllib re-entered the network.
        assert _RedirectingHandler.hits == ["/"]
        os.unlink(prof.name)
    finally:
        server.shutdown()
        thread.join(timeout=5)


# --------------------------------------------------------------------------- #
# DAS-1549 — T3 (C5): resolve-time SSRF block holds under a DNS-rebinding-
# style resolver (the guard resolves independently of the URL host string;
# pinning the vetted IP through to the actual connection is the documented
# future-hardening residual noted by the DAS-1547 red-team — non-blocking,
# recorded here rather than silently assumed away)
# --------------------------------------------------------------------------- #

def test_t3_dns_rebinding_style_resolution_is_blocked_at_resolve_time():
    """A 'rebinding' host is one whose resolved address the attacker controls
    and can flip. Model the WORST case directly: whatever the resolver hands
    back for THIS call is what gets vetted — an attacker who controls
    resolution to return an internal IP is blocked at resolve time, exactly
    once, before any request is made. (TOCTOU between this resolution and
    urllib's own later DNS lookup is a documented residual — pinning the
    vetted IP into the actual connection is tracked as future hardening, not
    asserted as fixed by this test.)"""
    rebinding_targets = ("169.254.169.254", "127.0.0.1", "10.1.2.3", "::1")
    for target in rebinding_targets:
        allowed, reason = egress.check_egress(
            "https://api.crossref.org/works",
            "research-read",
            PROFILES,
            resolver=_resolver_returning(target),
        )
        assert not allowed, f"a rebind to {target} must be blocked at resolve time"
        assert "internal" in reason


def test_t3_ipv6_mapped_and_unique_local_also_blocked():
    """Extra rebinding targets beyond the C5 basic set: IPv4-mapped IPv6
    loopback and an IPv6 unique-local range."""
    for target in ("::ffff:127.0.0.1", "fc00::1", "fe80::1"):
        allowed, reason = egress.check_egress(
            "https://api.crossref.org/works",
            "research-read",
            PROFILES,
            resolver=_resolver_returning(target),
        )
        assert not allowed, f"{target} must be blocked"
        assert "internal" in reason


# --------------------------------------------------------------------------- #
# DAS-1549 — T5 (C1): the drift guard detects a tampered/stale compiled
# allow-list (the inverse of test_c1_allowlist_matches_overlays_no_drift,
# which proves the CURRENT committed file has zero drift)
# --------------------------------------------------------------------------- #

def test_t5_tampered_allowlist_is_detected_as_drift():
    """A hand-edited (tampered) copy of the compiled map no longer equals a
    fresh recompile — proving the generate-and-diff mechanism WOULD catch a
    hand-edit as a red build, not merely that today's file happens to match."""
    gen = _load_gen_subagents()
    regenerated = gen.compile_tool_allowlist()
    tampered = dict(regenerated)
    tampered["mcp__playwright"] = ["ceo"]  # a hand-added, unreviewed grant
    assert tampered != regenerated, "a tampered map must diverge from the honest recompile"


def test_t5_stale_allowlist_missing_a_real_grant_is_detected_as_drift():
    """A STALE compiled file (an overlay grant added, generator not re-run)
    also diverges from a fresh recompile — the drift guard is not fooled by
    partial staleness either."""
    gen = _load_gen_subagents()
    overlay = """## External tools
```yaml
external_tools:
  - server: mcp__langchain-tools
    tools: ["web_fetch"]
    egress_profile: research-read
    reason: newly added grant not yet reflected in the committed file
```
"""
    fresh_with_new_overlay = gen.compile_tool_allowlist(
        [*gen.iter_overlays(), ("new-role-ic", overlay)]
    )
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    assert fresh_with_new_overlay != committed, (
        "a real overlay grant that hasn't been recompiled into the committed "
        "file must show up as drift"
    )


# --------------------------------------------------------------------------- #
# Sidecar build (mcp-dependent)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp not installed")
def test_sidecar_builds_and_registers_tool():
    server = bridge.build_server()
    assert server is not None
