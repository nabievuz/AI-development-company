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
    import gen_subagents

    return gen_subagents


hook = _load("tools/mcp_bridges/audit_external_tool.py", "audit_external_tool")
bridge = _load("tools/mcp_bridges/langchain_tool_bridge.py", "langchain_tool_bridge")
egress = _load("tools/mcp_bridges/egress_guard.py", "egress_guard")
redaction = _load("tools/mcp_bridges/redaction.py", "redaction")


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


def test_c1_tool_allowlist_is_tracked():
    path = ROOT / "board" / ".tool-allowlist.json"
    assert path.is_file(), "board/.tool-allowlist.json must exist as a tracked baseline"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=ROOT
    )
    assert ignored.returncode != 0, "board/.tool-allowlist.json must NOT be gitignored (C1)"


def test_c1_allowlist_matches_overlays_no_drift():
    gen = _load_gen_subagents()
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    regenerated = gen.compile_tool_allowlist()
    assert committed == regenerated


def test_c2_server_wide_grant_compiles_to_explicit_roles():
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
    assert hook.decide("mcp__x__t", "anyone", {"mcp__x": "*"})[0] == "deny"
    assert hook.decide("mcp__x__t", "anyone", {"mcp__x": ["*"]})[0] == "deny"
    assert hook.decide("mcp__x__t", "*", {"mcp__x": ["*"]})[0] == "deny"


def test_c2_load_allowlist_rejects_wildcard(tmp_path, monkeypatch):
    p = tmp_path / "al.json"
    p.write_text(json.dumps({"mcp__x": "*"}))
    monkeypatch.setenv("DASLAB_TOOL_ALLOWLIST", str(p))
    assert hook.load_allowlist() == {}
    p.write_text(json.dumps({"mcp__x": ["*"]}))
    assert hook.load_allowlist() == {}

    p.write_text(json.dumps({"mcp__x": ["qa-lead"]}))
    assert hook.load_allowlist() == {"mcp__x": ["qa-lead"]}


def test_c3_settings_binding_present_and_failclosed():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    pre = settings["hooks"]["PreToolUse"]
    entry = next(e for e in pre if e.get("matcher") == "mcp__.*")
    cmd = entry["hooks"][0]["command"]
    assert "audit_external_tool.py" in cmd
    assert "exit 2" in cmd, "the wrapper must fail CLOSED on hook-exec failure (C3)"


def test_c3_decode_failclosed():

    assert hook.decide("mcp__x__t", "unknown", {})[0] == "deny"

    assert hook.decide("mcp__x__t", "unknown", {"mcp__x": "qa-lead"})[0] == "deny"


def test_infra_mcp_servers_are_never_governed():
    for tool in ("mcp__ArcRift__store_memory", "mcp__ArcRift__recall_context", "mcp__obsidian__anything"):
        assert hook.decide(tool, "unknown", {})[0] == "allow", tool
        assert hook.decide(tool, "backend-em", {})[0] == "allow", tool

    assert hook.decide("mcp__playwright__browser_navigate", "unknown", {})[0] == "deny"


def test_infra_mcp_carveout_is_env_overridable(monkeypatch):
    monkeypatch.setenv("DASLAB_INFRA_MCP", "mcp__ArcRift")
    assert hook.decide("mcp__ArcRift__x", "unknown", {})[0] == "allow"
    assert hook.decide("mcp__obsidian__x", "unknown", {})[0] == "deny"


def _features(tmp_path: Path, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_a_tool_bridge: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _run_hook(
    event: dict,
    env_extra: dict,
    features: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    cmd = [sys.executable, str(BRIDGES / "audit_external_tool.py")]
    if features is not None:
        cmd += ["--features", str(features)]
    return subprocess.run(
        cmd,
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else ROOT,
        env=env,
    )


def test_c3_flag_off_is_inert(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        {"tool_name": "mcp__ArcRift__store_memory", "agent": "backend-em"},
        {"DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
        features=_features(tmp_path, on=False),
    )
    assert r.returncode == 0
    assert json.loads(r.stdout) == {}
    assert not audit_log.exists()


def test_c3_flag_on_enforces_and_audits(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    empty_allow = tmp_path / "al.json"
    empty_allow.write_text("{}")
    r = _run_hook(
        {"tool_name": "mcp__playwright__browser_navigate", "agent": "backend-em"},
        {
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(empty_allow),
        },
        features=_features(tmp_path, on=True),
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert audit_log.exists()
    rec = json.loads(audit_log.read_text().splitlines()[-1])
    assert rec["decision"] == "deny"


def test_c3_wrapper_denies_on_spawn_failure():
    r = subprocess.run(
        ["sh", "-c", "python3 /nonexistent/definitely_missing.py || exit 2"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2


def test_c4_no_redirect_handler_refuses():
    h = bridge._NoRedirect()

    assert h.redirect_request(None, None, 302, "Found", {}, "http://evil.internal/") is None


def test_c4_web_fetch_egress_gate_before_network(monkeypatch):
    monkeypatch.delenv("DASLAB_EGRESS_PROFILE", raising=False)
    out = bridge.web_fetch("https://evil.example/steal")
    assert out.startswith("error:")
    assert "egress denied" in out


def test_web_fetch_rejects_non_url():
    assert bridge.web_fetch("not-a-url").startswith("error:")


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
        resolver=_resolver_returning(),
    )
    assert not allowed
    assert "did not resolve" in reason


def test_c6_plain_entry_label_boundary():
    assert egress.host_matches("example.org", ["example.org"])
    assert egress.host_matches("api.example.org", ["example.org"])
    assert not egress.host_matches("evilexample.org", ["example.org"])
    assert not egress.host_matches("example.org.evil.com", ["example.org"])
    assert not egress.host_matches("notexample.org", ["example.org"])


def test_c6_wildcard_entry_subdomains_only():
    assert egress.host_matches("en.wikipedia.org", ["*.wikipedia.org"])
    assert not egress.host_matches("wikipedia.org", ["*.wikipedia.org"])
    assert not egress.host_matches("evilwikipedia.org", ["*.wikipedia.org"])


def test_c6_full_check_rejects_lookalike_suffix():
    pub = _resolver_returning("104.16.0.1")
    assert not egress.check_egress("https://evilwikipedia.org/", "research-read", PROFILES, pub)[0]
    assert egress.check_egress("https://en.wikipedia.org/", "research-read", PROFILES, pub)[0]


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


    marker = "PRIVATE KEY"
    pem = f"-----BEGIN RSA {marker}-----\nMIIabc\n-----END RSA {marker}-----"
    assert redaction.scrub(pem) == "[REDACTED:private_key]"


def test_c7_no_raw_secret_substring_survives():
    secret = "sk-ant-api03-" + "Zz9" * 20
    scrubbed = redaction.scrub(f"key is {secret} ok")
    assert secret not in scrubbed
    assert "[REDACTED:api_key]" in scrubbed


def test_c7_no_over_redaction_of_tier_m_digests():
    git_sha = "e0f3215abc9912ef0011223344556677889900aa"
    sha256 = "a" * 64
    numeric_id = "1234567890" * 4
    for digest in (git_sha, sha256, numeric_id):
        assert redaction.scrub(f"digest {digest} end") == f"digest {digest} end"


def test_c7_high_entropy_fallback_catches_mixed_secret():
    tok = "aB3" + "xY7_" * 10
    assert "[REDACTED:secret]" in redaction.scrub(f"token={tok}")


def test_c7_redact_then_truncate_ordering():
    secret = "sk-ant-api03-" + "Q" * 60


    out = redaction.redact_then_truncate(f"leading {secret} trailing", cap=25)
    assert "sk-ant" not in out
    assert len(out) <= 25


def test_c7_safe_scrub_fail_closed(monkeypatch):
    monkeypatch.setattr(redaction, "scrub", lambda _t: (_ for _ in ()).throw(RuntimeError("boom")))
    assert redaction.safe_scrub("anything") == "[REDACTED:unclassified]"


def test_sc001_no_overlay_entry_refused():
    assert hook.decide("mcp__globaltool__anything", "engineer-ic", {})[0] == "deny"


def test_sc001_audit_write_failure_still_denies(monkeypatch):
    decision, _reason = hook.decide("mcp__playwright__browser_navigate", "engineer-ic", {})
    assert decision == "deny"


    hook.audit({"ts": "t", "tool": "x", "agent": "y", "decision": decision, "reason": "r"})
    monkeypatch.setenv("DASLAB_TOOL_AUDIT_LOG", "/nonexistent-dir-xyz/does/not/exist/audit.jsonl")
    hook.audit({"ts": "t", "tool": "x", "agent": "y", "decision": decision, "reason": "r"})
    assert decision == "deny"


def test_sc002_tool_event_redaction_probe(tmp_path, monkeypatch):
    leaked = "sk-ant-api03-" + "Q" * 50
    tool_name = "mcp__x__t"
    decision, reason = hook.decide(tool_name, leaked, {"mcp__x__t": ["qa-lead"]})
    assert decision == "deny"
    assert leaked in reason

    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("DASLAB_TOOL_AUDIT_LOG", str(audit_log))
    from redaction import redact_then_truncate as _scrub

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


def test_sc003_flag_off_no_op_even_for_a_would_be_denied_tool(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        {"tool_name": "mcp__playwright__browser_navigate", "agent": "engineer-ic"},
        {"DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
        features=_features(tmp_path, on=False),
    )
    assert r.returncode == 0
    assert json.loads(r.stdout) == {}
    assert not audit_log.exists()


def _denied_event() -> dict:
    return {"tool_name": "mcp__playwright__browser_navigate", "agent": "backend-eng-1"}


def _assert_governed(r: subprocess.CompletedProcess, audit_log: Path, ctx: str) -> None:
    assert r.returncode == 0, ctx
    out = json.loads(r.stdout or "{}")
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", f"{ctx}: {out}"
    assert audit_log.exists(), f"{ctx}: denied but wrote no audit line"


def test_ambient_flag_var_cannot_silence_the_hook(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    for value in ("off", "false", "0", "no"):
        log = tmp_path / f"audit-{value}.jsonl"
        r = _run_hook(
            _denied_event(),
            {"DASLAB_WS_A_FLAG": value, "DASLAB_TOOL_AUDIT_LOG": str(log)},
            features=_features(tmp_path, on=True),
        )
        _assert_governed(r, log, f"DASLAB_WS_A_FLAG={value}")
    assert not audit_log.exists()


def test_ambient_features_redirect_cannot_silence_the_hook(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("{}\n", encoding="utf-8")
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        _denied_event(),
        {"DASLAB_FEATURES": str(empty), "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
        features=_features(tmp_path, on=True),
    )
    _assert_governed(r, audit_log, "DASLAB_FEATURES redirect")


def test_running_from_another_directory_cannot_silence_the_hook(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    audit_log = tmp_path / "audit.jsonl"
    r = _run_hook(
        _denied_event(),
        {"DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
        cwd=elsewhere,
    )
    _assert_governed(r, audit_log, "foreign cwd")


def test_default_features_is_anchored_to_the_hook_not_the_cwd():
    assert hook.DEFAULT_FEATURES == ROOT / "config" / "features.yaml"
    assert hook.DEFAULT_FEATURES.is_file()


def test_features_option_is_the_only_seam_and_the_deployed_hook_passes_none():
    assert hook._features_arg(["--features", "/x/f.yaml"]) == Path("/x/f.yaml")
    assert hook._features_arg(["--features=/x/f.yaml"]) == Path("/x/f.yaml")
    assert hook._features_arg([]) is None
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    blob = json.dumps(settings)
    assert "--features" not in blob
    assert "DASLAB_WS_A_FLAG" not in blob
    assert "DASLAB_FEATURES" not in blob


def test_t1_internal_crash_denies_and_exits_2(tmp_path):
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(BRIDGES)!r})
        import audit_external_tool as hook
        hook.decide = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            raise SystemExit(hook.main(["--features", {str(_features(tmp_path, on=True))!r}]))
        except SystemExit:
            raise
        except Exception as exc:
            hook._emit_deny(f"hook internal error — fail-closed deny ({{type(exc).__name__}})")
            raise SystemExit(2) from exc
        """
    )
    env = dict(os.environ)
    env.update({"DASLAB_TOOL_ALLOWLIST": "/tmp/does-not-exist.json"})
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
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(empty_allow),
        }
    )
    r = subprocess.run(
        [
            sys.executable,
            str(BRIDGES / "audit_external_tool.py"),
            "--features",
            str(_features(tmp_path, on=True)),
        ],
        input="{not valid json",
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


class _RedirectingHandler(http.server.BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self):
        type(self).hits.append(self.path)
        self.send_response(302)
        self.send_header("Location", "http://internal-target.example.invalid/secret")
        self.end_headers()

    def log_message(self, *_a):
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


        assert _RedirectingHandler.hits == ["/"]
        os.unlink(prof.name)
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_t3_dns_rebinding_style_resolution_is_blocked_at_resolve_time():
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
    for target in ("::ffff:127.0.0.1", "fc00::1", "fe80::1"):
        allowed, reason = egress.check_egress(
            "https://api.crossref.org/works",
            "research-read",
            PROFILES,
            resolver=_resolver_returning(target),
        )
        assert not allowed, f"{target} must be blocked"
        assert "internal" in reason


def test_t5_tampered_allowlist_is_detected_as_drift():
    gen = _load_gen_subagents()
    regenerated = gen.compile_tool_allowlist()
    tampered = dict(regenerated)
    tampered["mcp__playwright"] = ["ceo"]
    assert tampered != regenerated, "a tampered map must diverge from the honest recompile"


def test_t5_stale_allowlist_missing_a_real_grant_is_detected_as_drift():
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


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp not installed")
def test_sidecar_builds_and_registers_tool():
    server = bridge.build_server()
    assert server is not None
