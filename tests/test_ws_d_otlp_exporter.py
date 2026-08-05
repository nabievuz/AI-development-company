from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)

    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


exporter = _load("tools/observability/otlp_exporter.py", "ws_d_otlp_exporter_under_test")


def _base_span(**overrides):
    span = {
        "event_type": "span",
        "ticket_id": "DAS-1573",
        "trace_id": "DAS-1573",
        "span_id": "01J9ZB2K7Q0W9E4R5T6Y7U8ISP",
        "parent_span_id": None,
        "kind": "run",
        "gen_ai.agent.name": "backend-em",
        "gen_ai.request.model": "opus",
        "start": "2026-07-24T12:00:00Z",
        "end": "2026-07-24T12:03:20Z",
        "duration_ms": 200000,
        "gen_ai.usage.input_tokens": 18450,
        "gen_ai.usage.output_tokens": 5120,
        "gen_ai.usage.cached_input_tokens": 16000,
        "cached": True,
        "status": "ok",
        "created_at": "2026-07-24T12:03:20Z",
        "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
    }
    span.update(overrides)
    return span


def _write_features(tmp_path: Path, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_d_langfuse_lens: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _write_tenant(tmp_path: Path, langfuse_url: str) -> Path:
    p = tmp_path / "tenant_boundary.yaml"
    p.write_text(
        "version: 1\n"
        "accepted_external_roles:\n"
        "  - model\n"
        "endpoints:\n"
        "  - name: langfuse_observability\n"
        "    role: observability\n"
        "    carries_code_ip: true\n"
        f"    url: {langfuse_url}\n",
        encoding="utf-8",
    )
    return p


def _write_events(tmp_path: Path, spans: list[dict]) -> Path:
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(s) + "\n" for s in spans), encoding="utf-8")
    return p


def test_flag_off_is_inert_no_read_no_post(tmp_path):
    features = _write_features(tmp_path, on=False)
    events = _write_events(tmp_path, [_base_span()])
    tenant = _write_tenant(tmp_path, "http://127.0.0.1:3000")

    calls: list = []
    res = exporter.export_spans(
        events_path=events,
        config_path=tenant,
        features_path=features,
        transport=lambda t, p: calls.append((t, p)),
        post=True,
    )
    assert res.ran is False
    assert res.exported == 0
    assert res.read == 0
    assert res.target is None
    assert res.posted is False
    assert calls == []


def test_flag_on_reads_and_exports(tmp_path):
    features = _write_features(tmp_path, on=True)
    events = _write_events(tmp_path, [_base_span(), _base_span(span_id="second")])
    tenant = _write_tenant(tmp_path, "http://127.0.0.1:3000")

    res = exporter.export_spans(events_path=events, config_path=tenant, features_path=features)
    assert res.ran is True
    assert res.read == 2
    assert res.exported == 2
    assert res.dropped == 0
    assert res.posted is False


def test_span_maps_to_well_formed_otlp():
    otlp = exporter.map_span_to_otlp(_base_span())

    assert len(otlp["traceId"]) == 32
    assert len(otlp["spanId"]) == 16
    int(otlp["traceId"], 16)
    int(otlp["spanId"], 16)
    assert otlp["parentSpanId"] == ""
    assert otlp["name"] == "run"

    assert otlp["startTimeUnixNano"].isdigit()
    assert otlp["endTimeUnixNano"].isdigit()
    assert int(otlp["endTimeUnixNano"]) > int(otlp["startTimeUnixNano"])
    assert otlp["status"]["code"] == 1
    attrs = {a["key"]: a["value"] for a in otlp["attributes"]}
    assert attrs["gen_ai.operation.name"] == {"stringValue": "run"}
    assert attrs["gen_ai.agent.name"] == {"stringValue": "backend-em"}
    assert attrs["gen_ai.usage.input_tokens"] == {"intValue": "18450"}
    assert attrs["daslab.usage.cached"] == {"boolValue": True}
    assert attrs["daslab.span.duration_ms"] == {"intValue": "200000"}


def test_error_status_and_child_parent_map():
    child = _base_span(kind="execute_tool", parent_span_id="01J9ZB2K7Q0W9E4R5T6Y7U8ISP", status="error")
    otlp = exporter.map_span_to_otlp(child)
    assert otlp["parentSpanId"] != ""
    assert len(otlp["parentSpanId"]) == 16
    assert otlp["status"]["code"] == 2


def test_trace_id_is_pure_function_of_ticket():
    assert exporter.derive_trace_id("DAS-1573") == exporter.derive_trace_id("DAS-1573")
    assert exporter.derive_trace_id("DAS-1573") != exporter.derive_trace_id("DAS-1574")


def test_build_otlp_payload_shape():
    otlp = exporter.map_span_to_otlp(_base_span())
    payload = exporter.build_otlp_payload([otlp], run_id="RUN-1")
    rs = payload["resourceSpans"][0]
    assert rs["scopeSpans"][0]["spans"] == [otlp]
    res_attrs = {a["key"]: a["value"] for a in rs["resource"]["attributes"]}
    assert res_attrs["service.name"] == {"stringValue": "daslab"}
    assert res_attrs["daslab.run_id"] == {"stringValue": "RUN-1"}


def _planted_secret_blob() -> str:

    api_key = "sk-ant-" + "api03-" + "A" * 40
    aws = "AKIA" + "1234567890ABCDEF"
    bearer = "Bearer " + "abcDEF1234567890tokenval"
    jwt = "eyJ" + "abcdef123" + "." + "abcdef456" + "." + "sig7890xyz"
    pem = (
        "-----BEGIN " + "RSA PRIVATE KEY-----\n"
        "MIIabc" + "DEF123ghi456\n"
        "-----END " + "RSA PRIVATE KEY-----"
    )
    dsn = "postgres://" + "user" + ":" + "hunter2secret" + "@db.example.internal/app"
    email = "alice" + "@" + "example.com"
    return " ".join([api_key, aws, bearer, jwt, pem, dsn, email])


def test_redaction_on_export_scrubs_planted_secrets():
    blob = _planted_secret_blob()
    span = _base_span(**{"daslab.error_message": blob, "daslab.summary": "run " + blob})
    safe = exporter.redact_span(span)
    assert safe is not None

    otlp = exporter.map_span_to_otlp(safe)
    wire = json.dumps(exporter.build_otlp_payload([otlp]))


    for needle in [
        "sk-ant-" + "api03-",
        "AKIA" + "1234567890ABCDEF",
        "abcDEF1234567890tokenval",
        "hunter2secret",
        "alice" + "@" + "example.com",
        "PRIVATE KEY-----\n" + "MIIabc",
    ]:
        assert needle not in wire, needle

    assert "[REDACTED:" in wire


def test_tier_m_ids_not_over_redacted():


    span = _base_span()
    safe = exporter.redact_span(span)
    assert safe["span_id"] == span["span_id"]
    assert safe["trace_id"] == span["trace_id"]
    otlp = exporter.map_span_to_otlp(safe)

    assert otlp["traceId"] == exporter.derive_trace_id("DAS-1573")
    assert otlp["spanId"] == exporter.derive_span_id(span["span_id"])


def test_tier_b_redact_then_truncate_ordering():


    secret = "sk-ant-" + "api03-" + "Z" * 40
    long_free_text = ("x " * 200) + secret
    span = _base_span(**{"daslab.note": long_free_text})
    safe = exporter.redact_span(span)
    assert secret not in safe["daslab.note"]
    assert len(safe["daslab.note"]) <= 280


def test_scrubber_raise_drops_the_span(monkeypatch):

    red = exporter._redaction_mod()

    def _boom(_text):
        raise RuntimeError("scrubber exploded")

    monkeypatch.setattr(red, "scrub", _boom)
    span = _base_span(**{"daslab.free": "some free text attribute"})
    assert exporter.redact_span(span) is None


def test_scrubber_raise_span_dropped_in_export(tmp_path, monkeypatch):
    features = _write_features(tmp_path, on=True)
    tenant = _write_tenant(tmp_path, "http://127.0.0.1:3000")
    events = _write_events(tmp_path, [_base_span(**{"daslab.free": "text"})])

    red = exporter._redaction_mod()
    monkeypatch.setattr(red, "scrub", lambda _t: (_ for _ in ()).throw(RuntimeError("boom")))

    calls: list = []
    res = exporter.export_spans(
        events_path=events,
        config_path=tenant,
        features_path=features,
        transport=lambda t, p: calls.append(p),
        post=True,
    )
    assert res.read == 1
    assert res.dropped == 1
    assert res.exported == 0
    assert res.posted is False
    assert calls == []


def test_in_tenant_target_passes(tmp_path):
    tenant = _write_tenant(tmp_path, "http://127.0.0.1:3000")
    target = exporter.assert_in_tenant(tenant)
    assert target == "http://127.0.0.1:3000" + exporter.OTEL_TRACE_PATH

    assert exporter.resolve_target(tenant) == target
    assert exporter.endpoint_url(tenant) == "http://127.0.0.1:3000"


@pytest.mark.parametrize(
    "hosted",
    [
        "https://cloud.langfuse.com/api",
        "https://api.smith.langchain.com",
        "https://8.8.8.8:3000",
    ],
)
def test_hosted_endpoint_fails_closed(tmp_path, hosted):
    tenant = _write_tenant(tmp_path, hosted)
    with pytest.raises(exporter.BoundaryError):
        exporter.assert_in_tenant(tenant)


def test_export_blocks_before_post_on_hosted_target(tmp_path):
    features = _write_features(tmp_path, on=True)
    tenant = _write_tenant(tmp_path, "https://cloud.langfuse.com/api")
    events = _write_events(tmp_path, [_base_span()])

    calls: list = []
    with pytest.raises(exporter.BoundaryError):
        exporter.export_spans(
            events_path=events,
            config_path=tenant,
            features_path=features,
            transport=lambda t, p: calls.append(p),
            post=True,
        )
    assert calls == []


def test_rfc1918_and_local_names_are_in_tenant(tmp_path):
    for url in ["http://10.1.2.3:3000", "http://langfuse.internal:3000", "http://192.168.1.9:3000"]:
        tenant = _write_tenant(tmp_path, url)
        assert exporter.assert_in_tenant(tenant).endswith(exporter.OTEL_TRACE_PATH)


def test_exporter_exposes_no_event_store_write_path():
    src = (ROOT / "tools" / "observability" / "otlp_exporter.py").read_text(encoding="utf-8")


    assert "EventStore(" not in src
    assert "iter_events" in src
    assert 'event_type="span"' in src


    for write_mode in ('"w"', "'w'", '"a"', "'a'", '"w+"', '"a+"'):
        assert write_mode not in src


def test_export_does_not_mutate_the_events_file(tmp_path):
    features = _write_features(tmp_path, on=True)
    tenant = _write_tenant(tmp_path, "http://127.0.0.1:3000")
    events = _write_events(tmp_path, [_base_span(), _base_span(span_id="s2")])
    before = events.read_bytes()

    exporter.export_spans(events_path=events, config_path=tenant, features_path=features)
    assert events.read_bytes() == before
