from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from validate_commflows import (
    FLOWS_YAML,
    derive_expected_edges,
    emit_yaml,
    validate,
)


def _write(p: Path, data: object) -> Path:
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def test_committed_file_is_valid() -> None:
    assert validate(FLOWS_YAML) == []


def test_emit_is_idempotent_and_matches_committed_file() -> None:
    assert emit_yaml() == FLOWS_YAML.read_text(encoding="utf-8")


def test_derivation_has_two_edges_per_reporting_line() -> None:
    edges = derive_expected_edges()

    assert len(edges) == len(set(edges))
    dele = {(s, r) for s, r, k, _ in edges if k == "delegation"}
    esca = {(r, s) for s, r, k, _ in edges if k == "escalation"}
    assert dele == esca
    assert all(src == "routing.reports_to" for *_, src in edges)


def test_founder_never_a_node() -> None:
    edges = derive_expected_edges()
    assert all("founder" not in (s, r) for s, r, _, _ in edges)


def test_rejects_bad_kind(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"][0]["kind"] = "consult"
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("kind" in e for e in errs)


def test_rejects_bad_source(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"][0]["source"] = "made.up"
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("source" in e for e in errs)


def test_rejects_founder_as_node(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"].append(
        {
            "sender": "chairman",
            "receiver": "founder",
            "kind": "escalation",
            "source": "routing.reports_to",
        }
    )
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("founder" in e for e in errs)


def test_rejects_invented_edge(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"].append(
        {
            "sender": "seo-specialist",
            "receiver": "backend-eng-1",
            "kind": "delegation",
            "source": "routing.reports_to",
        }
    )
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("invented" in e for e in errs)


def test_rejects_missing_derived_edge(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"] = doc["flows"][:-2]
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("missing derived edge" in e for e in errs)


def test_rejects_dangling_role(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"][0]["sender"] = "no-such-role"
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("dangling" in e or "invented" in e for e in errs)


def test_rejects_unknown_field(tmp_path: Path) -> None:
    doc = yaml.safe_load(FLOWS_YAML.read_text(encoding="utf-8"))
    doc["flows"][0]["weight"] = 5
    errs = validate(_write(tmp_path / "f.yaml", doc))
    assert any("unknown field" in e for e in errs)


def test_rejects_empty_flows(tmp_path: Path) -> None:
    errs = validate(_write(tmp_path / "f.yaml", {"version": 1, "flows": []}))
    assert any("non-empty" in e for e in errs)
