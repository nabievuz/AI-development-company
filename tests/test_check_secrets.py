from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_secrets as cs

_LIVE_SAMPLES = {
    "openrouter_api_key": "sk-or-v1-" + "a" * 64,
    "anthropic_api_key": "sk-ant-api03-" + "A" * 48,
    "github_token": "gho_" + "B" * 36,
    "github_token_user": "ghu_" + "C" * 36,
    "github_token_server": "ghs_" + "D" * 36,
    "github_token_refresh": "ghr_" + "E" * 36,
    "github_token_classic": "ghp_" + "F" * 36,
    "github_fine_grained_token": "github_pat_" + "1" * 22 + "_" + "z" * 59,
    "slack_bot_token": "xoxb-123456789012-123456789012-" + "a" * 24,
    "slack_user_token": "xoxp-123456789012-123456789012-" + "b" * 24,
    "google_api_key": "AIza" + "S" * 35,
    "stripe_live_key": "sk_live_" + "9" * 24,
    "aws_access_key_id": "AKIA" + "Q" * 16,
}


@pytest.mark.parametrize("label,secret", sorted(_LIVE_SAMPLES.items()))
def test_every_org_key_format_is_detected(label: str, secret: str) -> None:
    assert cs.scan_text(f"token={secret}"), label


def test_private_key_block_still_detected() -> None:
    assert cs.scan_text("-----BEGIN OPENSSH PRIVATE KEY-----")


def test_benign_text_is_not_flagged() -> None:
    benign = "the wave dispatched DAS-1300 to sre-eng on sonnet; see board/.wave-log"
    assert cs.detect_secret_kinds(benign) == []


def test_detect_reports_the_kind() -> None:
    assert cs.detect_secret_kinds("sk-or-v1-" + "f" * 64) == ["openrouter_api_key"]


def test_scan_store_names_the_kind(tmp_path: Path) -> None:
    store = tmp_path / "e.jsonl"
    store.write_text(
        json.dumps({"id": "EV-1", "note": "key=sk-or-v1-" + "c" * 64}) + "\n",
        encoding="utf-8",
    )
    leaks = cs.scan_store(store)
    assert len(leaks) == 1
    assert "EV-1" in leaks[0]
    assert "openrouter_api_key" in leaks[0]


def test_cli_flags_openrouter_key_in_events(tmp_path: Path) -> None:
    store = tmp_path / "e.jsonl"
    store.write_text(json.dumps({"id": "EV-2", "v": "sk-or-v1-" + "d" * 64}) + "\n")
    rc = cs.main(["--events", str(store), "--experiments", str(tmp_path / "absent")])
    assert rc == cs.EXIT_LEAK


def test_cli_clean_store_is_ok(tmp_path: Path) -> None:
    store = tmp_path / "e.jsonl"
    store.write_text(json.dumps({"id": "EV-3", "v": "nothing secret here"}) + "\n")
    rc = cs.main(["--events", str(store), "--experiments", str(tmp_path / "absent")])
    assert rc == cs.EXIT_OK


def test_cli_nothing_to_scan_is_not_a_pass(tmp_path: Path) -> None:
    rc = cs.main([
        "--events", str(tmp_path / "absent.jsonl"),
        "--experiments", str(tmp_path / "absent-dir"),
    ])
    assert rc == cs.EXIT_NO_DATA
    assert rc != cs.EXIT_OK


def test_list_patterns_covers_the_org_key_formats(capsys: pytest.CaptureFixture[str]) -> None:
    assert cs.main(["--list-patterns"]) == cs.EXIT_OK
    printed = capsys.readouterr().out
    for kind in ("openrouter_api_key", "github_fine_grained_token", "slack_token",
                 "google_api_key", "stripe_live_key", "aws_access_key_id"):
        assert kind in printed
