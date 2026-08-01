"""WS-E in-tenant LiteLLM gateway + deferred vLLM/SGLang eject-path tests
(ADR-0038 / ADR-0009 / SPEC-006 FR-004, FR-005, DAS-1583).

Covers ``tools/model_gateway/`` against the design
(``docs/design/ws-e-tenant-hardening.md`` §4.1/§4.2):

  G1  the default gateway routes the Q9 Claude-subscription default in-tenant
      (role=model is the sole accepted external exception) and returns a
      well-formed GatewayCall whose admission decision came from the REUSED
      ADR-0009 admission layer (ws_b_admission.admit)
  G2  a hosted/external endpoint declared under a NON-model role fails closed
      at REGISTRATION time (GatewayConfigError) — never silently accepted
  G3  the same external endpoint fails closed at CALL time too (defense in
      depth) even if somehow present in the route table
  G4  an in-tenant (loopback/private) non-model-role endpoint IS accepted —
      TN-1 only blocks EXTERNAL code/IP, not in-tenant endpoints generally
  G5  gateway.call() propagates the ws_b_admission outcome vocabulary
      unchanged (REJECTED on empty model) — no re-implementation drift
  E1  ws_e_openweight_ejectpath OFF (the default) -> register_ejectpath /
      mock_call raise EjectPathInactiveError; the route is NEVER added to the
      gateway's route table (inertness, design §4.2 item (a))
  E2  ws_e_openweight_ejectpath ON (env override) -> registering + a mock
      call against a MOCK in-tenant endpoint succeeds and produces a
      well-formed GatewayCall — no live serving stack required
  E3  the eject-path route target MUST be in-tenant — an external URL is
      BLOCKED even with the sub-flag ON (design §4.2 item (b), "strengthens
      TN-1")
  E4  ws_e_tenant_hardening OFF alone (parent) keeps the eject-path inert
      even if the sub-flag env override is ON — nested gating
  E5  no agent-visible difference in call shape between the Claude route and
      the eject-path route (design §4.2 item (c)) — same GatewayCall shape
  F1  both flags OFF (repo defaults) -> flag.py resolves both False; gateway
      construction/import itself is unaffected (library, not wired to a live
      dispatch path) — flag-off byte-identical import behaviour
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# Fully-qualified (not bare `import gateway`/`import flag`): see
# ejectpath.py's comment on the sys.modules bare-name collision with sibling
# `tools/*` packages that ship a same-named module.
from tools.model_gateway import ejectpath as ep  # noqa: E402
from tools.model_gateway import flag as gw_flag  # noqa: E402
from tools.model_gateway import gateway as gw  # noqa: E402

EXTERNAL_HOSTED_URL = "https://code-hosting.example.com/v1/exec"
EXTERNAL_EJECTPATH_URL = "https://not-in-tenant.example.com:8000"
INTENANT_URL = "http://127.0.0.1:9999"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Never let a stray env var leak flag state between tests."""
    for var in (
        "DASLAB_WS_E_TENANT_HARDENING_FLAG",
        "DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG",
        "DASLAB_FEATURES",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def _features(tmp_path: Path, *, parent: bool, ejectpath: bool) -> Path:
    """A features file selecting both WS-E flags.

    The gateway honours no environment variable. A per-flag override and a
    DASLAB_FEATURES redirect were both removed: because the parent flag is
    committed ON, EITHER was enough on its own to open ws_e_openweight_ejectpath
    — the vLLM/SGLang eject-path ADR-0038 Q9 defers pending a Founder decision.
    """
    p = tmp_path / "features.yaml"
    p.write_text(
        f"ws_e_tenant_hardening: {'true' if parent else 'false'}\n"
        f"ws_e_openweight_ejectpath: {'true' if ejectpath else 'false'}\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# G1-G5 — the in-tenant LiteLLM gateway (FR-004, TN-1)
# ---------------------------------------------------------------------------


def test_g1_default_gateway_routes_claude_subscription_in_tenant():
    gateway = gw.default_gateway()
    route = gateway.resolve(gw.DEFAULT_CLAUDE_ROUTE_NAME)
    assert route.role == "model"
    assert route.auth == "account"
    assert route.url == "https://api.anthropic.com"

    call = gateway.call(
        route_name=gw.DEFAULT_CLAUDE_ROUTE_NAME,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="claude-sonnet-5",
    )
    assert isinstance(call, gw.GatewayCall)
    assert call.route.name == gw.DEFAULT_CLAUDE_ROUTE_NAME
    # The admission decision came from the REUSED ADR-0009 admission layer.
    assert call.admission.outcome.value == "admit"
    assert call.admission.admitted is True


def test_g2_external_non_model_endpoint_blocked_at_registration():
    gateway = gw.LiteLLMGateway(routes=())
    bad_route = gw.ModelRoute(
        name="rogue_code_endpoint",
        url=EXTERNAL_HOSTED_URL,
        role="sandbox",  # NOT "model" -> not the accepted exception
    )
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        gateway.register(bad_route)
    # Never made it into the route table.
    assert bad_route.name not in {r.name for r in gateway.routes()}


def test_g3_external_non_model_endpoint_blocked_at_call_time_defense_in_depth():
    # Bypass .register()'s guard to simulate a route that slipped into the
    # table some other way; .call() must independently re-check TN-1.
    gateway = gw.LiteLLMGateway(routes=())
    smuggled = gw.ModelRoute(name="smuggled", url=EXTERNAL_HOSTED_URL, role="tool")
    gateway._routes["smuggled"] = smuggled  # noqa: SLF001 - deliberate defense-in-depth probe
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        gateway.call(route_name="smuggled", ticket_id="DAS-1583", role="x", model="m")


def test_g4_in_tenant_non_model_endpoint_is_accepted():
    gateway = gw.LiteLLMGateway(routes=())
    ok_route = gw.ModelRoute(name="local_tool", url=INTENANT_URL, role="sandbox")
    gateway.register(ok_route)  # must NOT raise
    assert gateway.resolve("local_tool").url == INTENANT_URL


def test_g5_admission_outcome_vocabulary_propagates_unchanged():
    gateway = gw.default_gateway()
    call = gateway.call(
        route_name=gw.DEFAULT_CLAUDE_ROUTE_NAME,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="",  # empty -> ws_b_admission REJECTED (LAW 3)
    )
    assert call.admission.outcome.value == "rejected"
    assert call.admission.admitted is False


# ---------------------------------------------------------------------------
# E1-E5 — the DEFERRED vLLM/SGLang eject-path (FR-005), mock-endpoint only
# ---------------------------------------------------------------------------


def test_e1_ejectpath_inert_while_subflag_off(tmp_path):
    off = _features(tmp_path, parent=True, ejectpath=False)
    gateway = gw.default_gateway()
    with pytest.raises(ep.EjectPathInactiveError):
        ep.register_ejectpath(gateway, features_path=off)
    # Never registered -> resolving it fails as "no such route", not TN-1.
    with pytest.raises(gw.GatewayConfigError, match="no such gateway route"):
        gateway.resolve(ep.EJECTPATH_ROUTE_NAME)

    with pytest.raises(ep.EjectPathInactiveError):
        ep.mock_call(
            gateway,
            ticket_id="DAS-1583",
            role="backend-eng-1",
            model="local-llm",
            features_path=off,
        )


def test_e2_ejectpath_mock_call_succeeds_when_subflag_on(tmp_path):
    on = _features(tmp_path, parent=True, ejectpath=True)
    assert gw_flag.openweight_ejectpath_on(on) is True

    gateway = gw.default_gateway()
    backend = ep.OpenWeightBackend(url=ep.DEFAULT_MOCK_URL, engine="vllm")
    call = ep.mock_call(
        gateway,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="local-open-weight-model",
        backend=backend,
        features_path=on,
    )
    assert isinstance(call, gw.GatewayCall)
    assert call.route.name == ep.EJECTPATH_ROUTE_NAME
    assert call.route.url == ep.DEFAULT_MOCK_URL
    assert call.route.role == "ejectpath"
    assert call.admission.outcome.value == "admit"
    # The route is now genuinely registered on the gateway's table.
    assert gateway.resolve(ep.EJECTPATH_ROUTE_NAME).url == ep.DEFAULT_MOCK_URL


def test_e3_ejectpath_external_target_blocked_even_with_subflag_on(tmp_path):
    on = _features(tmp_path, parent=True, ejectpath=True)

    gateway = gw.default_gateway()
    external_backend = ep.OpenWeightBackend(url=EXTERNAL_EJECTPATH_URL, engine="sglang")
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        ep.register_ejectpath(gateway, backend=external_backend, features_path=on)
    assert ep.EJECTPATH_ROUTE_NAME not in {r.name for r in gateway.routes()}


def test_e4_parent_flag_off_keeps_ejectpath_inert_even_if_subflag_on(tmp_path):
    # Sub-flag ON alone, WITHOUT the parent, must not open the eject-path. The
    # committed parent flag is ON after activation, so it is forced OFF here to
    # test the nesting invariant deterministically.
    nested = _features(tmp_path, parent=False, ejectpath=True)
    assert gw_flag.tenant_hardening_on(nested) is False
    assert gw_flag.openweight_ejectpath_on(nested) is False

    gateway = gw.default_gateway()
    with pytest.raises(ep.EjectPathInactiveError):
        ep.register_ejectpath(gateway, features_path=nested)


def test_e5_ejectpath_call_shape_matches_claude_route_shape(tmp_path):
    on = _features(tmp_path, parent=True, ejectpath=True)

    gateway = gw.default_gateway()
    claude_call = gateway.call(
        route_name=gw.DEFAULT_CLAUDE_ROUTE_NAME,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="claude-sonnet-5",
    )
    eject_call = ep.mock_call(
        gateway,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="local-open-weight-model",
        features_path=on,
    )
    # Same dataclass shape/fields — swapping routes is a config change, not a
    # caller-visible type change (design §4.2 item (c)).
    assert type(claude_call) is type(eject_call)
    assert set(vars(claude_call)) == set(vars(eject_call))


# ---------------------------------------------------------------------------
# F1 — both flags OFF (repo defaults, no env override) -> inert
# ---------------------------------------------------------------------------


def test_f2_no_ambient_value_can_open_the_deferred_ejectpath(tmp_path, monkeypatch):
    """ADR-0038 Q9 DEFERS the eject-path pending a Founder decision, and the
    parent flag is committed ON — so a single ambient value used to be enough to
    open it on its own. Both doors are asserted shut, in both directions."""
    off = _features(tmp_path, parent=True, ejectpath=False)
    evil_dir = tmp_path / "evil"
    evil_dir.mkdir()
    evil = _features(evil_dir, parent=True, ejectpath=True)

    for value in ("true", "1", "on", "yes"):
        monkeypatch.setenv("DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG", value)
        monkeypatch.setenv("DASLAB_WS_E_TENANT_HARDENING_FLAG", value)
        assert gw_flag.openweight_ejectpath_on(off) is False, value
        with pytest.raises(ep.EjectPathInactiveError):
            ep.register_ejectpath(gw.default_gateway(), features_path=off)

    # A DASLAB_FEATURES redirect was a complete substitute for the flag override.
    monkeypatch.setenv("DASLAB_FEATURES", str(evil))
    assert gw_flag.openweight_ejectpath_on(off) is False
    # …and it cannot suppress a genuinely ON file either.
    monkeypatch.setenv("DASLAB_FEATURES", str(off))
    assert gw_flag.openweight_ejectpath_on(evil) is True


def test_f2_flag_file_is_anchored_to_the_package_not_the_cwd(tmp_path, monkeypatch):
    """The default used to be found by walking up from Path.cwd(), so the flag a
    caller saw depended on where the process happened to start."""
    assert gw_flag.DEFAULT_FEATURES == ROOT / "config" / "features.yaml"
    monkeypatch.chdir(tmp_path)
    assert gw_flag.tenant_hardening_on() is gw_flag._read_flag(
        gw_flag.TENANT_HARDENING_FLAG, ROOT / "config" / "features.yaml"
    )


def test_f2_parent_and_subflag_always_read_the_same_file(tmp_path):
    """Nesting is only meaningful if both legs come from one source — otherwise a
    mixed parent/sub read could satisfy the invariant from two different files."""
    nested = _features(tmp_path, parent=False, ejectpath=True)
    assert gw_flag.openweight_ejectpath_on(nested) is False
    both_dir = tmp_path / "both"
    both_dir.mkdir()
    both = _features(both_dir, parent=True, ejectpath=True)
    assert gw_flag.openweight_ejectpath_on(both) is True


def test_f1_default_gateway_is_flag_independent(tmp_path):
    # Force both WS-E flags OFF explicitly — the committed config now carries
    # ws_e_tenant_hardening ON after the 2026-07-26 Founder-authorized activation.
    off = _features(tmp_path, parent=False, ejectpath=False)
    assert gw_flag.tenant_hardening_on(off) is False
    assert gw_flag.openweight_ejectpath_on(off) is False
    # Constructing/using the near-term default gateway does not depend on
    # either flag — it is a plain library call (mirrors ws_b_admission.py).
    gateway = gw.default_gateway()
    assert gateway.resolve(gw.DEFAULT_CLAUDE_ROUTE_NAME).url == "https://api.anthropic.com"


def test_f1b_real_features_yaml_tenant_hardening_on_ejectpath_off():
    # Post-activation (2026-07-26): the parent flag is ON, the eject-path sub-flag
    # stays OFF (explicit-decision-only, nested under the parent).
    text = (ROOT / "config" / "features.yaml").read_text(encoding="utf-8")
    assert "ws_e_tenant_hardening: true" in text
    assert "ws_e_openweight_ejectpath: false" in text
