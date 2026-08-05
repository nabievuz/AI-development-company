from __future__ import annotations

import base64
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


exporter = _load("tools/observability/otlp_exporter.py", "ws_d_otlp_exporter_e2e")


class StubOtlpServer:

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": body,
                    }
                )
                payload = b'{"partialSuccess":{}}'
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> StubOtlpServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _span(**overrides) -> dict:
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
        "status": "ok",
        "created_at": "2026-07-24T12:03:20Z",
        "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
    }
    span.update(overrides)
    return span


def _features(tmp_path: Path, on: bool = True) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_d_langfuse_lens: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _tenant(tmp_path: Path, url: str) -> Path:
    p = tmp_path / "tenant_boundary.yaml"
    p.write_text(
        "version: 1\n"
        "accepted_external_roles:\n"
        "  - model\n"
        "endpoints:\n"
        "  - name: langfuse_observability\n"
        "    role: observability\n"
        "    carries_code_ip: true\n"
        f"    url: {url}\n",
        encoding="utf-8",
    )
    return p


def _events(tmp_path: Path, spans: list[dict]) -> Path:
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(s) + "\n" for s in spans), encoding="utf-8")
    return p


@pytest.fixture()
def langfuse_creds(monkeypatch):
    monkeypatch.setenv(exporter.LANGFUSE_PUBLIC_KEY_ENV, "pk-lf-public")
    monkeypatch.setenv(exporter.LANGFUSE_SECRET_KEY_ENV, "sk-lf-secret")
    monkeypatch.delenv(exporter.OTLP_BEARER_TOKEN_ENV, raising=False)
    return base64.b64encode(b"pk-lf-public:sk-lf-secret").decode("ascii")


def test_end_to_end_post_arrives_authenticated_with_otlp_body(tmp_path, langfuse_creds):
    with StubOtlpServer() as stub:
        result = exporter.export_spans(
            events_path=_events(tmp_path, [_span(), _span(span_id="second")]),
            config_path=_tenant(tmp_path, stub.base_url),
            features_path=_features(tmp_path),
            post=True,
        )

        assert result.outcome is exporter.ExportOutcome.EXPORTED
        assert result.posted is True
        assert result.exported == 2
        assert result.failed == 0
        assert result.last_error is None

        assert len(stub.requests) == 1
        sent = stub.requests[0]
        assert sent["path"] == exporter.OTEL_TRACE_PATH
        assert sent["headers"]["authorization"] == "Basic " + langfuse_creds
        assert sent["headers"]["content-type"] == "application/json"

        body = json.loads(sent["body"].decode("utf-8"))
        spans = body["resourceSpans"][0]["scopeSpans"][0]["spans"]
        assert len(spans) == 2
        assert len(spans[0]["traceId"]) == 32
        assert len(spans[0]["spanId"]) == 16
        assert spans[0]["startTimeUnixNano"].isdigit()
        resource = {
            a["key"]: a["value"] for a in body["resourceSpans"][0]["resource"]["attributes"]
        }
        assert resource["service.name"] == {"stringValue": "daslab"}


def test_bearer_credentials_are_used_when_langfuse_keys_are_absent(tmp_path, monkeypatch):
    monkeypatch.delenv(exporter.LANGFUSE_PUBLIC_KEY_ENV, raising=False)
    monkeypatch.delenv(exporter.LANGFUSE_SECRET_KEY_ENV, raising=False)
    monkeypatch.setenv(exporter.OTLP_BEARER_TOKEN_ENV, "otlp-token-value")

    with StubOtlpServer() as stub:
        result = exporter.export_spans(
            events_path=_events(tmp_path, [_span()]),
            config_path=_tenant(tmp_path, stub.base_url),
            features_path=_features(tmp_path),
            post=True,
        )
        assert result.posted is True
        assert stub.requests[0]["headers"]["authorization"] == "Bearer otlp-token-value"


def test_missing_credentials_fail_the_export_visibly_and_send_nothing(tmp_path, monkeypatch):
    for name in (
        exporter.LANGFUSE_PUBLIC_KEY_ENV,
        exporter.LANGFUSE_SECRET_KEY_ENV,
        exporter.OTLP_BEARER_TOKEN_ENV,
    ):
        monkeypatch.delenv(name, raising=False)

    with StubOtlpServer() as stub:
        result = exporter.export_spans(
            events_path=_events(tmp_path, [_span()]),
            config_path=_tenant(tmp_path, stub.base_url),
            features_path=_features(tmp_path),
            post=True,
        )
        assert result.outcome is exporter.ExportOutcome.EXPORT_FAILED
        assert result.posted is False
        assert result.failed == 1
        assert "ExportAuthError" in result.last_error
        assert stub.requests == []


def test_auth_headers_raises_when_no_credentials_are_configured():
    with pytest.raises(exporter.ExportAuthError):
        exporter.auth_headers({})


def test_nothing_to_export_is_distinguishable_from_export_failed(tmp_path, langfuse_creds):
    with StubOtlpServer() as stub:
        empty = exporter.export_spans(
            events_path=_events(tmp_path, []),
            config_path=_tenant(tmp_path, stub.base_url),
            features_path=_features(tmp_path),
            post=True,
        )
        assert empty.outcome is exporter.ExportOutcome.NOTHING_TO_EXPORT
        assert empty.post_attempted is False
        assert empty.failed == 0
        assert stub.requests == []

    with StubOtlpServer(status=500) as stub:
        broken = exporter.export_spans(
            events_path=_events(tmp_path, [_span()]),
            config_path=_tenant(tmp_path, stub.base_url),
            features_path=_features(tmp_path),
            transport=lambda t, p: exporter.http_post_transport(t, p, sleep=lambda _s: None),
            post=True,
        )
        assert broken.outcome is exporter.ExportOutcome.EXPORT_FAILED
        assert broken.post_attempted is True
        assert broken.failed == 1

    assert empty.outcome is not broken.outcome
    assert empty.posted == broken.posted is False


def test_unauthorized_response_is_not_retried(tmp_path, langfuse_creds):
    with StubOtlpServer(status=401) as stub:
        with pytest.raises(exporter.ExportTransportError) as excinfo:
            exporter.http_post_transport(
                stub.base_url + exporter.OTEL_TRACE_PATH,
                {"resourceSpans": []},
                sleep=lambda _s: None,
            )
        assert excinfo.value.status == 401
        assert excinfo.value.attempts == 1
        assert len(stub.requests) == 1


def test_server_error_is_retried_a_bounded_number_of_times(tmp_path, langfuse_creds):
    slept: list[float] = []
    with StubOtlpServer(status=503) as stub:
        with pytest.raises(exporter.ExportTransportError) as excinfo:
            exporter.http_post_transport(
                stub.base_url + exporter.OTEL_TRACE_PATH,
                {"resourceSpans": []},
                attempts=3,
                sleep=slept.append,
            )
        assert excinfo.value.attempts == 3
        assert len(stub.requests) == 3
        assert len(slept) == 2


def test_transport_failure_never_escapes_export_spans(tmp_path, langfuse_creds):
    def _boom(_target, _payload):
        raise OSError("connection reset")

    result = exporter.export_spans(
        events_path=_events(tmp_path, [_span()]),
        config_path=_tenant(tmp_path, "http://127.0.0.1:3000"),
        features_path=_features(tmp_path),
        transport=_boom,
        post=True,
    )
    assert result.outcome is exporter.ExportOutcome.EXPORT_FAILED
    assert result.failed == 1
    assert "connection reset" in result.last_error


def test_collect_without_post_is_its_own_outcome(tmp_path, langfuse_creds):
    result = exporter.export_spans(
        events_path=_events(tmp_path, [_span()]),
        config_path=_tenant(tmp_path, "http://127.0.0.1:3000"),
        features_path=_features(tmp_path),
    )
    assert result.outcome is exporter.ExportOutcome.COLLECTED_NOT_POSTED
    assert result.posted is False
    assert result.failed == 0


def test_flag_off_outcome_is_disabled(tmp_path):
    result = exporter.export_spans(
        events_path=_events(tmp_path, [_span()]),
        config_path=_tenant(tmp_path, "http://127.0.0.1:3000"),
        features_path=_features(tmp_path, on=False),
        post=True,
    )
    assert result.outcome is exporter.ExportOutcome.DISABLED
    assert result.ran is False


def test_cli_exit_code_separates_export_failure_from_no_data(tmp_path, langfuse_creds, capsys):
    tenant = _tenant(tmp_path, "http://127.0.0.1:3000")
    features = _features(tmp_path)

    no_data = exporter.main(
        [
            "--post",
            "--events", str(_events(tmp_path, [])),
            "--config", str(tenant),
            "--features", str(features),
        ]
    )
    assert no_data == exporter.EXIT_OK
    assert "outcome=nothing_to_export" in capsys.readouterr().out

    with StubOtlpServer(status=500) as stub:
        code = exporter.main(
            [
                "--post",
                "--events", str(_events(tmp_path, [_span()])),
                "--config", str(_tenant(tmp_path, stub.base_url)),
                "--features", str(features),
            ]
        )
    assert code == exporter.EXIT_EXPORT_FAILED
    captured = capsys.readouterr()
    assert "outcome=export_failed" in captured.out
    assert "failed=1" in captured.out
    assert captured.err.strip()


def test_cli_help_does_not_treat_the_flag_as_a_path(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exporter.main(["--help"])
    assert excinfo.value.code == 0
    assert "--post" in capsys.readouterr().out
