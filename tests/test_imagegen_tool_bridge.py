"""imagegen sidecar tests (DAS-1645 / ADR-0033 edge, reused).

``tools/mcp_bridges/imagegen_tool_bridge.py`` arrived wired but untested: it is
the org's FIRST bridge carrying a production credential and the FIRST path to a
non-Anthropic model, and every other sidecar in ``tools/mcp_bridges/`` has
coverage. These tests pin the invariants that make the two firsts containable —
none of them require the network or an API key.

  P1  a prompt carrying an ADR-0012 §2 secret/PII shape is REFUSED, not scrubbed
      (a silently scrubbed prompt renders the wrong image; a disclosed one leaks)
  P2  out_path is contained under the generated-media root (no absolute, no
      ``..`` escape, extension allow-list) — the tool is not a file-write primitive
  P3  the model is pinned to the reviewed set
  P4  the credential is read from the environment only, and never reaches the
      returned transcript on any path
  P5  the TB-4 egress gate runs BEFORE any network syscall, and a denial is
      terminal
  P6  redirects are never followed (C4)
  P7  the function never raises — a failure is tool output, not a dead wave
  P8  provider bytes are size-capped, and the file is retargeted rather than
      mislabelled when the provider's encoding disagrees with the extension
"""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGES = ROOT / "tools" / "mcp_bridges"


def _load_bridge():
    """Import the sidecar by path (it is launched by path, not as a package)."""
    if str(BRIDGES) not in sys.path:
        sys.path.insert(0, str(BRIDGES))
    spec = importlib.util.spec_from_file_location(
        "_imagegen_tool_bridge", BRIDGES / "imagegen_tool_bridge.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_imagegen_tool_bridge"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_bridge()


@pytest.fixture
def sandbox(mod, monkeypatch, tmp_path):
    """Point the generated-media root at tmp_path and supply a dummy credential.

    ``_out_root`` derives from the module's own file location, so the root is
    redirected by env var rather than by writing into the real ``projects/``.
    """
    monkeypatch.setenv("DASLAB_IMAGEGEN_OUT_ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "_out_root", lambda: tmp_path.resolve())
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-" + "t" * 32)
    # Default posture for the happy path: egress allowed. Individual tests
    # override this to assert the gate.
    monkeypatch.setattr(mod, "check_egress", lambda url, profile: (True, ""))
    monkeypatch.setattr(mod, "active_profile", lambda: "imagegen-openrouter")
    return tmp_path


def _png_data_url(payload: bytes = b"\x89PNG\r\n\x1a\nfake", mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(payload).decode()


def _provider_response(url: str) -> dict:
    return {"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}


class _FakeResponse:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self, _limit=None):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub_opener(mod, monkeypatch, payload: dict, spy: list | None = None):
    """Replace the module opener so no test ever reaches the network."""

    class _Opener:
        def open(self, request, timeout=None):
            if spy is not None:
                spy.append(request)
            return _FakeResponse(payload)

    monkeypatch.setattr(mod, "_OPENER", _Opener())


# --------------------------------------------------------------------------- #
# P1 — the prompt is disclosed to a third party, so it is refused, not scrubbed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-" + "A" * 40,
        "AKIA" + "A" * 16,
        "ghp_" + "b" * 30,
        "sk-or-v1-" + "c" * 32,
        "reach me at founder@example.com",
        "call +1 415 555 0142 first",
    ],
)
def test_prompt_carrying_a_forbidden_shape_is_refused(mod, sandbox, monkeypatch, secret):
    # The opener asserts on use: a refusal that still reached the network — i.e.
    # disclosed the very prompt it refused — is the bug this pins.
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image(f"a poster, {secret}", "out.png")
    assert result.startswith("error: prompt refused")
    assert "contains" in result


def _never_opened():
    class _Boom:
        def open(self, request, timeout=None):  # pragma: no cover - must not run
            raise AssertionError("network reached despite a refused prompt")

    return _Boom()


def test_refusal_names_the_shape_but_never_echoes_the_secret(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    secret = "ghp_" + "z" * 30
    result = mod.generate_image(f"logo {secret}", "out.png")
    assert "API_KEY" in result
    assert secret not in result, "the refusal echoed the credential it refused"


def test_a_clean_prompt_is_not_refused(mod, sandbox, monkeypatch):
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url()))
    result = mod.generate_image("a calm blue landscape, wide", "clean.png")
    assert result.startswith("imagegen: wrote"), result


def test_empty_and_oversized_prompts_are_rejected(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    assert mod.generate_image("   ", "out.png") == "error: prompt is required"
    too_long = "x" * (mod._MAX_PROMPT_CHARS + 1)
    assert "exceeds" in mod.generate_image(too_long, "out.png")


# --------------------------------------------------------------------------- #
# P2 — containment: this writes images, it is not a file-write primitive
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_path",
    [
        "/etc/cron.d/pwn.png",
        "../../escape.png",
        "sub/../../../escape.png",
        "\\windows\\evil.png",
    ],
)
def test_out_path_escapes_are_refused(mod, sandbox, monkeypatch, bad_path):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image("a poster", bad_path)
    assert result.startswith("error:")
    assert "relative" in result or "escapes" in result


def test_out_path_is_required(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    assert "out_path is required" in mod.generate_image("a poster", "")


@pytest.mark.parametrize("bad_ext", ["notes.txt", "script.sh", "payload.py", "noext"])
def test_out_path_extension_allowlist(mod, sandbox, monkeypatch, bad_ext):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image("a poster", bad_ext)
    assert "must end in" in result


@pytest.mark.parametrize("good_ext", ["a.png", "b.jpg", "c.jpeg", "d.webp"])
def test_allowed_extensions_resolve(mod, sandbox, good_ext):
    resolved, error = mod._resolve_out_path(good_ext)
    assert error == "" and resolved is not None


def test_a_contained_nested_path_is_written_under_the_root(mod, sandbox, monkeypatch):
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url()))
    result = mod.generate_image("a hero image", "site/public/media/hero.png")
    assert result.startswith("imagegen: wrote")
    written = sandbox / "site" / "public" / "media" / "hero.png"
    assert written.is_file(), result


# --------------------------------------------------------------------------- #
# P3 — the model is pinned to the reviewed set
# --------------------------------------------------------------------------- #


def test_unreviewed_model_is_refused(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image("a poster", "out.png", model="openai/dall-e-3")
    assert "not in the reviewed set" in result


def test_model_env_override_is_also_gated_by_the_allowlist(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    monkeypatch.setenv("DASLAB_IMAGEGEN_MODEL", "some/unreviewed-model")
    assert "not in the reviewed set" in mod.generate_image("a poster", "out.png")


@pytest.mark.parametrize("model", sorted({"google/gemini-3-pro-image-preview", "google/gemini-2.5-flash-image"}))
def test_every_reviewed_model_is_accepted(mod, sandbox, monkeypatch, model):
    assert model in mod._ALLOWED_MODELS, "the reviewed set changed — update the policy too"
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url()))
    result = mod.generate_image("a poster", "out.png", model=model)
    assert result.startswith("imagegen: wrote") and model in result


# --------------------------------------------------------------------------- #
# P4 — the credential lives in the environment and never in the transcript
# --------------------------------------------------------------------------- #


def test_missing_key_is_a_plain_error_not_a_traceback(mod, sandbox, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image("a poster", "out.png")
    assert result == "error: OPENROUTER_API_KEY is not set — add it to .env (never commit it)"


def test_the_key_is_sent_as_a_bearer_header_and_never_returned(mod, sandbox, monkeypatch):
    key = "sk-or-v1-" + "k" * 40
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    spy: list = []
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url()), spy=spy)
    result = mod.generate_image("a poster", "out.png")
    assert result.startswith("imagegen: wrote")
    assert key not in result, "the success line leaked the credential"
    # It did travel — as a header, not as a body field or a query parameter.
    request = spy[0]
    assert request.get_header("Authorization") == f"Bearer {key}"
    assert key not in request.full_url
    assert key.encode() not in request.data


def test_the_key_is_never_accepted_as_a_tool_argument(mod):
    import inspect

    params = set(inspect.signature(mod.generate_image).parameters)
    assert params == {"prompt", "out_path", "model", "aspect_ratio"}, (
        "the tool signature grew a parameter — a credential must never be one"
    )


def test_a_provider_http_error_body_is_scrubbed_before_it_is_returned(mod, sandbox, monkeypatch):
    import urllib.error

    leaked = "upstream said: contact ops@example.com about key sk-or-v1-" + "q" * 32

    class _Boom:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(
                mod._ENDPOINT, 402, "Payment Required", {}, _BodyFile(leaked.encode())
            )

    monkeypatch.setattr(mod, "_OPENER", _Boom())
    result = mod.generate_image("a poster", "out.png")
    assert result.startswith("error: provider HTTP 402")
    assert "ops@example.com" not in result, "a third-party error body reached the transcript unscrubbed"


class _BodyFile:
    """Minimal file-like for HTTPError's fp argument."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self, limit=None):
        return self._data[:limit] if limit else self._data

    def close(self):
        return None


# --------------------------------------------------------------------------- #
# P5 — the egress gate runs before the network, and a denial is terminal
# --------------------------------------------------------------------------- #


def test_egress_denial_blocks_the_call_entirely(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "check_egress", lambda url, profile: (False, "egress denied: openrouter.ai"))
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    result = mod.generate_image("a poster", "out.png")
    assert result == "error: egress denied: openrouter.ai"


def test_egress_is_checked_against_the_pinned_endpoint(mod, sandbox, monkeypatch):
    seen: list = []

    def _spy(url, profile):
        seen.append((url, profile))
        return True, ""

    monkeypatch.setattr(mod, "check_egress", _spy)
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url()))
    mod.generate_image("a poster", "out.png")
    assert seen == [(mod._ENDPOINT, "imagegen-openrouter")]
    assert mod._ENDPOINT.startswith("https://openrouter.ai/")


def test_egress_denial_writes_no_file(mod, sandbox, monkeypatch):
    monkeypatch.setattr(mod, "check_egress", lambda url, profile: (False, "denied"))
    monkeypatch.setattr(mod, "_OPENER", _never_opened())
    mod.generate_image("a poster", "nothing.png")
    assert not (sandbox / "nothing.png").exists()


# --------------------------------------------------------------------------- #
# P6 — redirects are never followed (C4)
# --------------------------------------------------------------------------- #


def test_the_opener_refuses_every_redirect(mod):
    handler = mod._NoRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, "http://169.254.169.254/") is None
    for code in (301, 302, 303, 307, 308):
        assert handler.redirect_request(None, None, code, "", {}, "http://example.com") is None


def test_the_module_opener_is_built_with_the_no_redirect_handler(mod):
    assert any(isinstance(h, mod._NoRedirect) for h in mod._OPENER.handlers)


# --------------------------------------------------------------------------- #
# P7 — never raises: a failure is tool output, not a dead wave
# --------------------------------------------------------------------------- #


def test_an_arbitrary_transport_exception_becomes_an_error_string(mod, sandbox, monkeypatch):
    class _Boom:
        def open(self, request, timeout=None):
            raise OSError("Network is unreachable")

    monkeypatch.setattr(mod, "_OPENER", _Boom())
    result = mod.generate_image("a poster", "out.png")
    assert result.startswith("error: ") and "unreachable" in result


def test_a_text_only_provider_answer_is_reported_not_raised(mod, sandbox, monkeypatch):
    _stub_opener(mod, monkeypatch, {"choices": [{"message": {"content": "I cannot draw that."}}]})
    result = mod.generate_image("a poster", "out.png")
    assert result.startswith("error: provider returned text, not an image")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"images": []}}]},
        {"choices": [{"message": {"images": [{"image_url": {}}]}}]},
    ],
)
def test_malformed_provider_payloads_return_an_error(mod, sandbox, monkeypatch, payload):
    _stub_opener(mod, monkeypatch, payload)
    result = mod.generate_image("a poster", "out.png")
    assert result.startswith("error:"), result


def test_a_non_data_image_url_is_refused(mod, sandbox, monkeypatch):
    _stub_opener(mod, monkeypatch, _provider_response("https://cdn.example.com/img.png"))
    result = mod.generate_image("a poster", "out.png")
    assert "non-data image URL" in result


def test_an_undecodable_payload_is_reported(mod):
    raw, _mime, error = mod._decode_data_url("data:image/png;base64,")
    assert raw is None and "empty image payload" in error


# --------------------------------------------------------------------------- #
# P8 — size cap and honest file labelling
# --------------------------------------------------------------------------- #


def test_an_oversized_image_is_capped(mod, sandbox, monkeypatch):
    huge = b"\x00" * (mod._MAX_BYTES + 1)
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url(huge)))
    result = mod.generate_image("a poster", "big.png")
    assert "exceeds" in result and "MB cap" in result
    assert not (sandbox / "big.png").exists(), "an over-cap image was written anyway"


def test_a_mime_mismatch_retargets_the_file_instead_of_mislabelling_it(mod, sandbox, monkeypatch):
    # Requested .png, provider returned JPEG bytes: writing JPEG into a .png
    # breaks every downstream consumer silently.
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url(b"\xff\xd8\xffjpegbytes", "image/jpeg")))
    result = mod.generate_image("a poster", "hero.png")
    assert "retargeted to .jpg" in result
    assert (sandbox / "hero.jpg").is_file()
    assert not (sandbox / "hero.png").exists()


def test_a_matching_mime_is_not_retargeted(mod, sandbox, monkeypatch):
    _stub_opener(mod, monkeypatch, _provider_response(_png_data_url(b"pngbytes", "image/png")))
    result = mod.generate_image("a poster", "hero.png")
    assert "retargeted" not in result
    assert (sandbox / "hero.png").is_file()


def test_the_summary_keeps_the_size_readable_instead_of_scrubbing_it(mod):
    # The scrubber's PHONE shape eats a bare 7-digit byte count; the summary must
    # report a unit-bearing size the caller can actually read.
    line = mod._summary(Path("a/b.png"), 1_468_306, "google/gemini-3-pro-image-preview", "")
    assert "REDACTED" not in line
    assert "1.4 MB" in line
    small = mod._summary(Path("a/b.png"), 4096, "google/gemini-2.5-flash-image", "")
    assert "4 KB" in small


def test_a_display_path_outside_the_repo_does_not_raise(mod, tmp_path, monkeypatch):
    # DASLAB_IMAGEGEN_OUT_ROOT may legitimately point outside the repo (a worktree
    # writing into the main checkout). relative_to() raises on that; the contract
    # is never-raise, AFTER the bytes were already paid for.
    outside = tmp_path / "elsewhere" / "img.png"
    monkeypatch.setattr(mod, "_out_root", lambda: tmp_path)
    assert mod._display_path(outside) == Path("elsewhere/img.png")
    monkeypatch.setattr(mod, "_out_root", lambda: Path("/nonexistent-root"))
    assert mod._display_path(outside) == outside  # falls back, does not raise


# --------------------------------------------------------------------------- #
# Wiring — the admission surface this sidecar depends on
# --------------------------------------------------------------------------- #


def test_the_tool_is_declared_in_the_compiled_allowlist(mod):
    allowlist = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text(encoding="utf-8"))
    grants = allowlist.get("mcp__imagegen__generate_image")
    assert grants, "the sidecar is not admitted through the TB-2 allow-list"
    assert "*" not in grants, "a wildcard role grant would defeat the fail-closed allow-list"


def test_the_egress_profile_names_exactly_one_host(mod):
    import yaml

    profiles = yaml.safe_load((ROOT / "config" / "egress-allowlist.yaml").read_text(encoding="utf-8"))
    section = profiles.get("profiles", profiles)
    domains = section.get("imagegen-openrouter")
    assert domains == ["openrouter.ai"], f"the profile was widened in place: {domains}"
