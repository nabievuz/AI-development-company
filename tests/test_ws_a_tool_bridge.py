"""WS-A tool-bridge tests (ADR-0033 / DAS-1547).

Positive + negative unit coverage for the GATE-2 security conditions C1–C7.
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
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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
# Sidecar build (mcp-dependent)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp not installed")
def test_sidecar_builds_and_registers_tool():
    server = bridge.build_server()
    assert server is not None
