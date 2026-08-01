#!/usr/bin/env python3
"""DasLab — image-generation sidecar (OpenRouter), admitted through the ADR-0033 edge.

A FastMCP sidecar (ADR-0033 TB-1) exposing text-to-image generation as a
governed MCP tool, admitted through the *same* edge WS-A built
(``audit_external_tool.py`` PreToolUse hook + the compiled TB-2 allow-list) and
gated by the *same* TB-4 egress guard ``langchain_tool_bridge.web_fetch`` uses.
No second admission path, no second egress path (ADR-0010 C1).

**Two firsts, and why they are contained.**

1. *First bridge carrying a production credential.* Every sidecar before this
   one is deny-all and credential-free. ``OPENROUTER_API_KEY`` is read from the
   environment, never accepted as an argument, never echoed, and never written
   to the returned transcript. A missing key is a plain error, not a traceback.

2. *First non-Anthropic model in the org.* The Model Allocation Law governs
   which Claude model an AGENT runs on; this is a TOOL an agent calls, so that
   law is untouched. The provider-facing rules live in
   ``governance/policies/third-party-model-tools.md``.

**Prompt egress is a disclosure, not a fetch.** Unlike ``web_fetch``, this tool
SENDS caller-authored text to a third party. A prompt carrying a credential or
personal data would leak it, and a silently scrubbed prompt would render the
wrong image — so this module REFUSES a prompt that trips the ADR-0012 §2
secret/PII shapes rather than mangling it. The caller fixes the prompt.

**Images never enter the transcript.** The tool returns a repo-relative FILE
PATH. Tool transcripts are redact-then-truncate'd (ADR-0012 §2); a megabyte of
base64 there would be both useless to the reader and a redaction hazard.

Egress: ``imagegen-openrouter`` — a single host, ``openrouter.ai``. Adding it
was a reviewed ``security_sensitive`` + ``governance_or_policy`` change to
``config/egress-allowlist.yaml`` (QONUN-5), and the profile is never widened in
place.

**Known limitation — the profile is server-scoped, not role-scoped.** Overlays
declare ``egress_profile:`` per role, but nothing in this repo yet injects
``DASLAB_EGRESS_PROFILE`` at launch time from the invoking role: today it is set
only in tests, and every shipped profile is deny-all, so the gap has never
mattered. This is the first sidecar needing a non-empty profile, so the profile
is pinned in ``.mcp.json`` and therefore applies to any caller of THIS server.
Role granularity still holds — the TB-2 PreToolUse allow-list (fail-closed,
explicit role list, no wildcards) denies every role that did not declare the
grant before this module runs — but the second layer is host-scoped only. Wiring
per-role injection so the overlay field becomes load-bearing is tracked as
follow-up work in ``governance/policies/third-party-model-tools.md`` §5.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Sibling modules (egress guard, scrubber) live beside this file. When the
# sidecar is launched by path, that directory is not implicitly importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egress_guard import active_profile, check_egress  # noqa: E402
from redaction import redact_then_truncate  # noqa: E402

TOOL_NAME = "imagegen"

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_ENV_KEY = "OPENROUTER_API_KEY"
_ENV_MODEL = "DASLAB_IMAGEGEN_MODEL"
_ENV_OUT_ROOT = "DASLAB_IMAGEGEN_OUT_ROOT"

# Nano Banana Pro. Overridable per call; the default is the quality tier because
# these are brand assets, not throwaway drafts.
_DEFAULT_MODEL = "google/gemini-3-pro-image-preview"
_ALLOWED_MODELS = {
    "google/gemini-3-pro-image-preview",
    "google/gemini-2.5-flash-image",
}

# Generated files land under this repo-relative root unless overridden. Keeping
# writes inside one known directory is what makes the traversal check below a
# containment guarantee rather than a hint.
_DEFAULT_OUT_ROOT = "projects"

_MAX_PROMPT_CHARS = 4000
_MAX_BYTES = 40 * 1024 * 1024
_TIMEOUT_SECONDS = 180

# ADR-0012 §2 shapes that must never be disclosed to a third-party provider.
# Deliberately the SAME classes the scrubber and the Presidio sidecar know, so
# "what counts as sensitive" has one definition across the org.
_FORBIDDEN_IN_PROMPT: list[tuple[str, re.Pattern[str]]] = [
    ("API_KEY", re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OPENROUTER_KEY", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+\b")),
    ("PHONE", re.compile(r"(?<![\w.])\+?\d[\d ().\-]{7,15}\d(?![\w.])")),
]

_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """C4 — refuse to follow ANY 3xx redirect.

    An allow-listed host could 302 to an arbitrary (possibly internal) target,
    bypassing the egress gate that only ran against the ORIGINAL url.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _repo_root() -> Path:
    """Repo root — this file lives at ``<root>/tools/mcp_bridges/``."""
    return Path(os.path.abspath(__file__)).parents[2]


def _out_root() -> Path:
    rel = os.environ.get(_ENV_OUT_ROOT, "") or _DEFAULT_OUT_ROOT
    return (_repo_root() / rel).resolve()


def _resolve_out_path(out_path: str) -> tuple[Path | None, str]:
    """Resolve *out_path* under the configured root, or explain the refusal.

    Absolute paths and ``..`` escapes are refused: a tool that writes bytes
    anywhere the agent names is a file-write primitive, not an image generator.
    """
    candidate = (out_path or "").strip()
    if not candidate:
        return None, "error: out_path is required (repo-relative, e.g. 'sale.rentmarket.uz/public/media/hero.png')"
    if candidate.startswith(("/", "\\")) or ":" in candidate.split("/")[0]:
        return None, "error: out_path must be relative, not absolute"

    root = _out_root()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"error: out_path escapes the generated-media root ({root.name}/)"

    if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None, "error: out_path must end in .png, .jpg or .webp"
    return resolved, ""


def _check_prompt(prompt: str) -> str:
    """Return an error string if the prompt must not leave the org, else ""."""
    hits = [label for label, pattern in _FORBIDDEN_IN_PROMPT if pattern.search(prompt)]
    if hits:
        return (
            f"error: prompt refused — it contains {', '.join(sorted(set(hits)))}. "
            "This tool discloses the prompt to a third-party provider, so the "
            "prompt is refused rather than silently scrubbed (which would render "
            "the wrong image). Remove the value and retry."
        )
    return ""


def _decode_data_url(url: str) -> tuple[bytes | None, str, str]:
    """Decode a ``data:image/...;base64,...`` URL.

    Returns ``(raw_bytes, mime, error)`` — exactly one of ``raw_bytes`` and
    ``error`` is meaningful.
    """
    if not url.startswith("data:"):
        return None, "", "error: provider returned a non-data image URL"
    header, _, payload = url.partition(",")
    if not payload:
        return None, "", "error: provider returned an empty image payload"
    mime = header[5:].split(";")[0] or "image/png"
    try:
        raw = base64.b64decode(payload, validate=False)
    except Exception:
        return None, mime, "error: provider image payload was not valid base64"
    if not raw:
        return None, mime, "error: provider returned an empty image payload"
    if len(raw) > _MAX_BYTES:
        return None, mime, f"error: image exceeds the {_MAX_BYTES // (1024 * 1024)}MB cap"
    return raw, mime, ""


def _first_image_url(payload: dict) -> tuple[str, str]:
    """Pull the first image out of an OpenRouter chat-completions response.

    Handles both shapes the API returns: ``message.images[]`` and an image part
    inside ``message.content[]``. Returns ``(url, error)``.
    """
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", "error: provider returned no choices"
    message = (choices[0] or {}).get("message") or {}

    images = message.get("images")
    if isinstance(images, list):
        for item in images:
            url = ((item or {}).get("image_url") or {}).get("url")
            if isinstance(url, str) and url:
                return url, ""

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            url = ((part or {}).get("image_url") or {}).get("url")
            if isinstance(url, str) and url:
                return url, ""

    # A refusal or a text-only answer is the common non-image outcome; surface
    # the provider's own words (redacted) instead of a bare failure.
    if isinstance(content, str) and content.strip():
        return "", f"error: provider returned text, not an image — {redact_then_truncate(content, 400)}"
    return "", "error: provider returned no image"


def _summary(relative: Path, size_bytes: int, model: str, note: str) -> str:
    """Build the success line.

    Deliberately NOT run through ``redact_then_truncate``: every part is a value
    this module constructed — a containment-checked relative path, a file size
    and a pinned model id — so there is nothing to scrub, and the scrubber's
    PHONE shape happily eats a 7-digit byte count ("1468306" → ``[REDACTED:pii]``),
    destroying the one number the caller needs. Sizes are printed with a unit,
    which also keeps them out of digit-run territory. Only a length cap remains.
    """
    if size_bytes >= 1024 * 1024:
        size = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size = f"{size_bytes / 1024:.0f} KB"
    return f"imagegen: wrote {relative} ({size}, {model}){note}"[:500]


def generate_image(prompt: str, out_path: str, model: str = "", aspect_ratio: str = "") -> str:
    """Generate an image from *prompt* and write it to *out_path*.

    Args:
        prompt: What to draw. Sent verbatim to a third-party provider, so a
            prompt containing a credential, email or phone number is refused.
        out_path: Destination, RELATIVE to the generated-media root
            (``projects/`` by default) — e.g.
            ``sale.rentmarket.uz/public/media/hero.png``. Absolute paths and
            ``..`` escapes are refused.
        model: Optional. ``google/gemini-3-pro-image-preview`` (default, quality)
            or ``google/gemini-2.5-flash-image`` (cheap drafts).
        aspect_ratio: Optional, e.g. ``16:9``. A PROMPT HINT ONLY — it is
            appended as text, not passed as a generation parameter, and the
            model is free to ignore it. Verified 2026-08-01: a ``16:9`` hint to
            ``gemini-2.5-flash-image`` still returned 1024×1024. Resize or crop
            downstream if the aspect ratio has to be exact.

    Returns a one-line ``imagegen: wrote <path> (<n> bytes, <model>)`` summary,
    or an ``error: ...`` string. Never raises — a failure must not kill the wave.
    """
    text = prompt if isinstance(prompt, str) else str(prompt)
    text = text.strip()
    if not text:
        return "error: prompt is required"
    if len(text) > _MAX_PROMPT_CHARS:
        return f"error: prompt exceeds {_MAX_PROMPT_CHARS} characters"

    refusal = _check_prompt(text)
    if refusal:
        return refusal

    chosen = (model or os.environ.get(_ENV_MODEL, "") or _DEFAULT_MODEL).strip()
    if chosen not in _ALLOWED_MODELS:
        return f"error: model {chosen!r} is not in the reviewed set ({', '.join(sorted(_ALLOWED_MODELS))})"

    destination, path_error = _resolve_out_path(out_path)
    if destination is None:
        return path_error

    api_key = os.environ.get(_ENV_KEY, "").strip()
    if not api_key:
        return f"error: {_ENV_KEY} is not set — add it to .env (never commit it)"

    # TB-4 egress check BEFORE any network syscall (C5/C6). Deny-all by default.
    allowed, reason = check_egress(_ENDPOINT, active_profile())
    if not allowed:
        return f"error: {reason}"

    if aspect_ratio.strip():
        text = f"{text}\n\nAspect ratio: {aspect_ratio.strip()}."

    body = json.dumps(
        {
            "model": chosen,
            "messages": [{"role": "user", "content": text}],
            "modalities": ["image", "text"],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        _ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter attributes usage to these; they carry no secret.
            "HTTP-Referer": "https://daslab.local",
            "X-Title": "DasLab imagegen sidecar",
        },
    )

    try:
        with _OPENER.open(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(_MAX_BYTES).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", "replace") if hasattr(exc, "read") else ""
        return f"error: provider HTTP {exc.code} — {redact_then_truncate(detail, 400)}"
    except Exception as exc:  # surface any failure as tool output, never crash the wave
        return f"error: {redact_then_truncate(str(exc), 400)}"

    url, image_error = _first_image_url(payload)
    if image_error:
        return image_error

    raw, mime, decode_error = _decode_data_url(url)
    if raw is None:
        return decode_error

    # The caller chose the extension; the provider chose the encoding. Writing
    # PNG bytes into a .jpg would break every downstream consumer silently, so
    # retarget the file rather than mislabel it.
    expected = _EXT_BY_MIME.get(mime, "")
    note = ""
    if expected and destination.suffix.lower() not in {expected, ".jpeg" if expected == ".jpg" else expected}:
        destination = destination.with_suffix(expected)
        note = f" [retargeted to {expected} — provider returned {mime}]"

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    except OSError as exc:
        return f"error: could not write {destination.name} — {exc.strerror or exc}"

    relative = destination.relative_to(_repo_root())
    return _summary(relative, len(raw), chosen, note)


def build_server():
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is testable without it."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(generate_image)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab image-generation sidecar (ADR-0033 edge, reused)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
