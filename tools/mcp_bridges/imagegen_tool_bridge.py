#!/usr/bin/env python3

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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egress_guard import active_profile, check_egress
from redaction import redact_then_truncate

TOOL_NAME = "imagegen"

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_ENV_KEY = "OPENROUTER_API_KEY"
_ENV_MODEL = "DASLAB_IMAGEGEN_MODEL"
_ENV_OUT_ROOT = "DASLAB_IMAGEGEN_OUT_ROOT"


_DEFAULT_MODEL = "google/gemini-3-pro-image-preview"
_ALLOWED_MODELS = {
    "google/gemini-3-pro-image-preview",
    "google/gemini-2.5-flash-image",
}


_DEFAULT_OUT_ROOT = "projects"

_MAX_PROMPT_CHARS = 4000
_MAX_BYTES = 40 * 1024 * 1024
_TIMEOUT_SECONDS = 180


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

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _repo_root() -> Path:
    return Path(os.path.abspath(__file__)).parents[2]


def _out_root() -> Path:
    rel = os.environ.get(_ENV_OUT_ROOT, "") or _DEFAULT_OUT_ROOT
    return (_repo_root() / rel).resolve()


def _resolve_out_path(out_path: str) -> tuple[Path | None, str]:
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


    if isinstance(content, str) and content.strip():
        return "", f"error: provider returned text, not an image — {redact_then_truncate(content, 400)}"
    return "", "error: provider returned no image"


def _display_path(destination: Path) -> Path:
    for base in (_repo_root(), _out_root()):
        try:
            return destination.relative_to(base)
        except ValueError:
            continue
    return destination


def _summary(relative: Path, size_bytes: int, model: str, note: str) -> str:
    if size_bytes >= 1024 * 1024:
        size = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size = f"{size_bytes / 1024:.0f} KB"
    return f"imagegen: wrote {relative} ({size}, {model}){note}"[:500]


def generate_image(prompt: str, out_path: str, model: str = "", aspect_ratio: str = "") -> str:
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
    except Exception as exc:
        return f"error: {redact_then_truncate(str(exc), 400)}"

    url, image_error = _first_image_url(payload)
    if image_error:
        return image_error

    raw, mime, decode_error = _decode_data_url(url)
    if raw is None:
        return decode_error


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

    return _summary(_display_path(destination), len(raw), chosen, note)


def build_server():
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
