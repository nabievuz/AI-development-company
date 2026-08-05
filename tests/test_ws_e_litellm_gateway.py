from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


from tools.model_gateway import ejectpath as ep
from tools.model_gateway import flag as gw_flag
from tools.model_gateway import gateway as gw

EXTERNAL_HOSTED_URL = "https://code-hosting.example.com/v1/exec"
EXTERNAL_EJECTPATH_URL = "https://not-in-tenant.example.com:8000"
INTENANT_URL = "http://127.0.0.1:9999"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "DASLAB_WS_E_TENANT_HARDENING_FLAG",
        "DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG",
        "DASLAB_FEATURES",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def _features(tmp_path: Path, *, parent: bool, ejectpath: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(
        f"ws_e_tenant_hardening: {'true' if parent else 'false'}\n"
        f"ws_e_openweight_ejectpath: {'true' if ejectpath else 'false'}\n",
        encoding="utf-8",
    )
    return p


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

    assert call.admission.outcome.value == "admit"
    assert call.admission.admitted is True


def test_g2_external_non_model_endpoint_blocked_at_registration():
    gateway = gw.LiteLLMGateway(routes=())
    bad_route = gw.ModelRoute(
        name="rogue_code_endpoint",
        url=EXTERNAL_HOSTED_URL,
        role="sandbox",
    )
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        gateway.register(bad_route)

    assert bad_route.name not in {r.name for r in gateway.routes()}


def test_g3_external_non_model_endpoint_blocked_at_call_time_defense_in_depth():


    gateway = gw.LiteLLMGateway(routes=())
    smuggled = gw.ModelRoute(name="smuggled", url=EXTERNAL_HOSTED_URL, role="tool")
    gateway._routes["smuggled"] = smuggled
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        gateway.call(route_name="smuggled", ticket_id="DAS-1583", role="x", model="m")


def test_g4_in_tenant_non_model_endpoint_is_accepted():
    gateway = gw.LiteLLMGateway(routes=())
    ok_route = gw.ModelRoute(name="local_tool", url=INTENANT_URL, role="sandbox")
    gateway.register(ok_route)
    assert gateway.resolve("local_tool").url == INTENANT_URL


def test_g5_admission_outcome_vocabulary_propagates_unchanged():
    gateway = gw.default_gateway()
    call = gateway.call(
        route_name=gw.DEFAULT_CLAUDE_ROUTE_NAME,
        ticket_id="DAS-1583",
        role="backend-eng-1",
        model="",
    )
    assert call.admission.outcome.value == "rejected"
    assert call.admission.admitted is False


def test_e1_ejectpath_inert_while_subflag_off(tmp_path):
    off = _features(tmp_path, parent=True, ejectpath=False)
    gateway = gw.default_gateway()
    with pytest.raises(ep.EjectPathInactiveError):
        ep.register_ejectpath(gateway, features_path=off)

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

    assert gateway.resolve(ep.EJECTPATH_ROUTE_NAME).url == ep.DEFAULT_MOCK_URL


def test_e3_ejectpath_external_target_blocked_even_with_subflag_on(tmp_path):
    on = _features(tmp_path, parent=True, ejectpath=True)

    gateway = gw.default_gateway()
    external_backend = ep.OpenWeightBackend(url=EXTERNAL_EJECTPATH_URL, engine="sglang")
    with pytest.raises(gw.GatewayConfigError, match="TN-1 BLOCK"):
        ep.register_ejectpath(gateway, backend=external_backend, features_path=on)
    assert ep.EJECTPATH_ROUTE_NAME not in {r.name for r in gateway.routes()}


def test_e4_parent_flag_off_keeps_ejectpath_inert_even_if_subflag_on(tmp_path):


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


    assert type(claude_call) is type(eject_call)
    assert set(vars(claude_call)) == set(vars(eject_call))


def test_f2_no_ambient_value_can_open_the_deferred_ejectpath(tmp_path, monkeypatch):
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


    monkeypatch.setenv("DASLAB_FEATURES", str(evil))
    assert gw_flag.openweight_ejectpath_on(off) is False

    monkeypatch.setenv("DASLAB_FEATURES", str(off))
    assert gw_flag.openweight_ejectpath_on(evil) is True


def test_f2_flag_file_is_anchored_to_the_package_not_the_cwd(tmp_path, monkeypatch):
    assert gw_flag.DEFAULT_FEATURES == ROOT / "config" / "features.yaml"
    monkeypatch.chdir(tmp_path)
    assert gw_flag.tenant_hardening_on() is gw_flag._read_flag(
        gw_flag.TENANT_HARDENING_FLAG, ROOT / "config" / "features.yaml"
    )


def test_f2_parent_and_subflag_always_read_the_same_file(tmp_path):
    nested = _features(tmp_path, parent=False, ejectpath=True)
    assert gw_flag.openweight_ejectpath_on(nested) is False
    both_dir = tmp_path / "both"
    both_dir.mkdir()
    both = _features(both_dir, parent=True, ejectpath=True)
    assert gw_flag.openweight_ejectpath_on(both) is True


def test_f1_default_gateway_is_flag_independent(tmp_path):


    off = _features(tmp_path, parent=False, ejectpath=False)
    assert gw_flag.tenant_hardening_on(off) is False
    assert gw_flag.openweight_ejectpath_on(off) is False


    gateway = gw.default_gateway()
    assert gateway.resolve(gw.DEFAULT_CLAUDE_ROUTE_NAME).url == "https://api.anthropic.com"


def test_f1b_real_features_yaml_tenant_hardening_on_ejectpath_off():


    text = (ROOT / "config" / "features.yaml").read_text(encoding="utf-8")
    assert "ws_e_tenant_hardening: true" in text
    assert "ws_e_openweight_ejectpath: false" in text
