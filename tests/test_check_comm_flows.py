
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_comm_flows import (
    InputError,
    check_routes,
    extract_ticket_routes,
    load_declared_routes,
    load_dispatch_routes,
    main,
    parse_route_token,
    scan_tickets,
)


_FLOWS_YAML = textwrap.dedent(
    """\
    version: 1
    flows:
      - sender: backend-em
        receiver: cto
        kind: escalation
        source: routing.reports_to
      - sender: cto
        receiver: backend-em
        kind: delegation
        source: routing.reports_to
    """
)


def write_flows(tmp_path: Path, content: str = _FLOWS_YAML) -> Path:
    path = tmp_path / "communication-flows.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def write_ticket(tickets_dir: Path, name: str, routes_line: str | None) -> Path:
    tickets_dir.mkdir(parents=True, exist_ok=True)
    fm = ["---", "id: DAS-9001", "status: in_review"]
    if routes_line is not None:
        fm.append(f"routes: {routes_line}")
    fm += ["---", "", "## Description", "body", ""]
    path = tickets_dir / name
    path.write_text("\n".join(fm), encoding="utf-8")
    return path


def test_load_declared_routes(tmp_path: Path) -> None:
    declared = load_declared_routes(write_flows(tmp_path))
    assert ("backend-em", "cto") in declared
    assert ("cto", "backend-em") in declared

    assert ("backend-em", "backend-em") not in declared


def test_load_declared_routes_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        load_declared_routes(tmp_path / "nope.yaml")


def test_load_declared_routes_empty_flows_raises(tmp_path: Path) -> None:
    bad = write_flows(tmp_path, "version: 1\nflows: []\n")
    with pytest.raises(InputError):
        load_declared_routes(bad)


@pytest.mark.parametrize("tok", ["a>b", "a->b", "a→b", " a > b ", "`a`>`b`"])
def test_parse_route_token_variants(tok: str) -> None:
    assert parse_route_token(tok) == ("a", "b")


@pytest.mark.parametrize("tok", ["a", "a>b>c", ">b", "a>", ""])
def test_parse_route_token_bad(tok: str) -> None:
    with pytest.raises(ValueError):
        parse_route_token(tok)


def test_extract_ticket_routes_single() -> None:
    text = "---\nid: DAS-1\nroutes: backend-em>cto\n---\nbody\n"
    assert extract_ticket_routes(text) == [("backend-em", "cto")]


def test_extract_ticket_routes_list() -> None:
    text = "---\nid: DAS-1\nroutes: [backend-em>cto, cto->backend-em]\n---\nbody\n"
    assert extract_ticket_routes(text) == [("backend-em", "cto"), ("cto", "backend-em")]


def test_extract_ticket_routes_none() -> None:
    assert extract_ticket_routes("---\nid: DAS-1\n---\nbody\n") == []


def test_extract_ticket_routes_malformed_raises() -> None:
    with pytest.raises(ValueError):
        extract_ticket_routes("---\nroutes: not-a-route\n---\n")


def test_check_routes_declared_ok() -> None:
    declared = {("backend-em", "cto")}
    assert check_routes([("t", ("backend-em", "cto"))], declared) == []


def test_check_routes_undeclared_caught() -> None:
    declared = {("backend-em", "cto")}
    errs = check_routes([("t", ("ceo", "backend-em"))], declared)
    assert len(errs) == 1
    assert "undeclared route (ceo -> backend-em)" in errs[0]


def test_load_dispatch_routes(tmp_path: Path) -> None:
    path = tmp_path / "wave.json"
    path.write_text('[{"sender":"cto","receiver":"backend-em"}]', encoding="utf-8")
    assert load_dispatch_routes(path) == [("cto", "backend-em")]


def test_load_dispatch_routes_bad_shape(tmp_path: Path) -> None:
    path = tmp_path / "wave.json"
    path.write_text('[{"sender":"cto"}]', encoding="utf-8")
    with pytest.raises(InputError):
        load_dispatch_routes(path)


def test_scan_tickets_collects_and_flags(tmp_path: Path) -> None:
    tickets = tmp_path / "tickets"
    write_ticket(tickets, "DAS-1.md", "backend-em>cto")
    write_ticket(tickets, "DAS-2.md", None)
    write_ticket(tickets, "DAS-3.md", "garbage")
    refs, errs = scan_tickets(tickets)
    assert ("DAS-1.md", ("backend-em", "cto")) in refs
    assert any("DAS-3.md" in e for e in errs)


def test_main_clean_board_exit0(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    tickets = tmp_path / "tickets"
    write_ticket(tickets, "DAS-1.md", "backend-em>cto")
    write_ticket(tickets, "DAS-2.md", None)
    rc = main(["--flows", str(flows), "--tickets", str(tickets)])
    assert rc == 0


def test_main_undeclared_ticket_exit1(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    tickets = tmp_path / "tickets"
    write_ticket(tickets, "DAS-9.md", "ceo>backend-em")
    rc = main(["--flows", str(flows), "--tickets", str(tickets)])
    assert rc == 1


def test_main_missing_tickets_dir_exit2(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    rc = main(["--flows", str(flows), "--tickets", str(tmp_path / "nope")])
    assert rc == 2


def test_main_missing_flows_exit2(tmp_path: Path) -> None:
    rc = main(["--flows", str(tmp_path / "nope.yaml"), "--tickets", str(tmp_path)])
    assert rc == 2


def test_main_route_declared_exit0(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    rc = main(["--flows", str(flows), "--route", "cto>backend-em"])
    assert rc == 0


def test_main_route_undeclared_exit1(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    rc = main(["--flows", str(flows), "--route", "ceo>backend-em"])
    assert rc == 1


def test_main_route_bad_token_exit2(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    rc = main(["--flows", str(flows), "--route", "garbage"])
    assert rc == 2


def test_main_dispatch_undeclared_exit1(tmp_path: Path) -> None:
    flows = write_flows(tmp_path)
    dispatch = tmp_path / "wave.json"
    dispatch.write_text('[{"sender":"ceo","receiver":"backend-em"}]', encoding="utf-8")
    rc = main(["--flows", str(flows), "--dispatch", str(dispatch)])
    assert rc == 1


_REAL_FLOWS = _REPO_ROOT / "governance" / "communication-flows.yaml"
_REAL_AGENTS = _REPO_ROOT / ".claude" / "agents"
_ROUTE_LINE_RE = re.compile(r"^- (?:delegation|escalation) → `([a-z0-9-]+)`", re.MULTILINE)


def _shim_route_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for shim in _REAL_AGENTS.glob("*.md"):
        sender = shim.stem
        for receiver in _ROUTE_LINE_RE.findall(shim.read_text(encoding="utf-8")):
            pairs.add((sender, receiver))
    return pairs


@pytest.mark.skipif(not _REAL_FLOWS.exists(), reason="flows file not in-tree")
def test_real_shims_only_carry_declared_routes() -> None:
    declared = load_declared_routes(_REAL_FLOWS)
    shim_pairs = _shim_route_pairs()
    assert shim_pairs, "expected route sections in generated shims"
    undeclared = shim_pairs - declared
    assert not undeclared, f"shims carry undeclared routes: {sorted(undeclared)}"


@pytest.mark.skipif(not _REAL_FLOWS.exists(), reason="flows file not in-tree")
def test_undeclared_route_unrepresentable_in_shims() -> None:
    declared = load_declared_routes(_REAL_FLOWS)
    assert ("ceo", "backend-em") not in declared
    assert ("ceo", "backend-em") not in _shim_route_pairs()


@pytest.mark.skipif(not _REAL_FLOWS.exists(), reason="flows file not in-tree")
def test_real_board_passes(tmp_path: Path) -> None:
    rc = main([])
    assert rc == 0
