#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import check_approved_goal_queue as approved_queue
from _paths import ROOT

MANIFEST_NAME = "PROJECT-OS.yaml"
QUEUE_NAME = "APPROVED-GOAL-QUEUE.md"
DISCOVERY_REL = Path("docs") / "01-planning" / "discovery.md"
RESEARCH_REL = Path("docs") / "01-planning" / "RESEARCH-ENRICHMENT.md"


REQUIRED_MANIFEST_KEYS = ("name", "mission", "constraints", "stack", "budget", "success_metrics")
KNOWN_MANIFEST_KEYS = frozenset(REQUIRED_MANIFEST_KEYS)


CANONICAL_STAGE_DIRS = (
    "01-planning",
    "02-design",
    "03-development",
    "04-testing",
    "05-deployment",
    "06-maintenance",
)


AADL_STAGES = (
    (1, "Planning", "GATE-1", "01-planning", "senior-pm",
     "measurable business KPI defined, scope explicit, budget + risk-ethics signed off"),
    (2, "Design", "GATE-2", "02-design", "backend-em",
     "framework ADR merged, model card with cost/latency, guardrails cover OWASP LLM Top 10, security-lead sign-off"),
    (3, "Development", "GATE-3", "03-development", "backend-eng-1",
     "topography doc matches code, tool contracts documented, dev env reproducible, model layer hot-swappable"),
    (4, "Testing", "GATE-4", "04-testing", "qa-eng",
     "eval suite automated in CI with thresholds, integration tests green, red-team findings fixed, qa-lead sign-off"),
    (5, "Deployment", "GATE-5", "05-deployment", "sre-eng",
     "guardrails verified live, traces + cost per transaction visible, kill-switch armed — NO launch with GATE-5 open"),
    (6, "Maintenance", "GATE-6", "06-maintenance", "product-analyst",
     "KPI vs Stage-1 baseline reported, cost/value positive, feedback entering eval set"),
)


COMPILABLE_QUEUE_STATUSES = frozenset({"founder_approved", "planned", "active"})


_PLACEHOLDER_RES = (
    (re.compile(r"\bTODO\b"), "TODO"),
    (re.compile(r"\bFIXME\b"), "FIXME"),
    (re.compile(r"\bTBD\b"), "TBD"),
    (re.compile(r"\bXXX\b"), "XXX"),
    (re.compile(r"\[NEEDS CLARIFICATION"), "[NEEDS CLARIFICATION]"),
    (re.compile(r"<\.\.\.>"), "<...>"),
    (re.compile(r"<[A-Z][A-Z0-9_]{2,}>"), "<PLACEHOLDER_TOKEN>"),
)


_RELAX_VERB_RE = re.compile(
    r"\b(waiv\w*|skip\w*|bypass\w*|disabl\w*|ignor\w*|relax\w*|loosen\w*|"
    r"weaken\w*|exempt\w*|opt[\s-]?out|override|remov\w*)\b",
    re.IGNORECASE,
)
_ORG_LAW_NOUN_RE = re.compile(
    r"\b(qonun|gate|gate-[1-6]|security|compliance|policy|law|never[\s-]?auto[\s-]?approve|"
    r"approval|review|guardrail|aadl|precedence)\b",
    re.IGNORECASE,
)


_Q_RE = re.compile(r"(?im)^\s*Q\d*\s*[:.)]")
_A_RE = re.compile(r"(?im)^\s*A\d*\s*[:.)]")
_WAIVER_RE = re.compile(r"\b(WAIV(?:ED|ER)|DISCOVERY[\s_-]?WAIVED)\b", re.IGNORECASE)


DISCOVERY_QUESTIONS = (
    "Who is the target user, and in what context do they hit the core problem?",
    "What is the single must-have outcome the product must deliver?",
    "What is explicitly a non-goal (out of scope) for v1?",
    "What is the business model and how does the product make or save money?",
    "What are the measurable success metrics (KPIs) and their targets?",
    "What is the hard deadline or launch window?",
    "What is the token/compute and money budget ceiling?",
    "What existing assets (code, data, brand, accounts) can the project reuse?",
    "What integrations or third-party systems must it connect to?",
    "What compliance, legal, or data-residency constraints apply?",
    "Where does it deploy and under what domain / infra?",
    "What are the support and availability expectations?",
    "What is the risk tolerance (failure modes, worst-case loop cost)?",
)

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class PackError:

    file: str
    field: str
    problem: str
    fix: str

    def __str__(self) -> str:
        loc = self.file if not self.field else f"{self.file} :: {self.field}"
        return f"{loc}\n      problem: {self.problem}\n      fix:     {self.fix}"


@dataclass
class StageResult:
    name: str
    ok: bool
    detail: str


@dataclass
class PipelineResult:
    slug: str
    ok: bool = False
    rejected_stage: str | None = None
    errors: list[PackError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    research_path: Path | None = None
    tickets: list[Path] = field(default_factory=list)
    stages: list[StageResult] = field(default_factory=list)

    def _stage(self, name: str, ok: bool, detail: str) -> None:
        self.stages.append(StageResult(name, ok, detail))


def _pack_text_files(pack_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in (MANIFEST_NAME, "README.md", QUEUE_NAME):
        p = pack_root / rel
        if p.is_file():
            files.append(p)
    docs = pack_root / "docs"
    if docs.is_dir():
        files.extend(sorted(p for p in docs.rglob("*") if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}))
    return files


def _lint_placeholders(pack_root: Path, errors: list[PackError]) -> None:
    for f in _pack_text_files(pack_root):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pat, label in _PLACEHOLDER_RES:
                if pat.search(line):
                    errors.append(PackError(
                        file=str(f.relative_to(pack_root)),
                        field=f"line {lineno}",
                        problem=f"unfilled placeholder marker {label!r}: {line.strip()[:80]!r}",
                        fix=f"replace the {label} slot with a real value before submitting the pack",
                    ))


_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _lint_links(pack_root: Path, errors: list[PackError]) -> None:
    for f in _pack_text_files(pack_root):
        if f.suffix != ".md":
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for target in _LINK_RE.findall(text):
            target = target.strip().split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")) or not target:
                continue
            rel = target.split("#", 1)[0]
            if not rel:
                continue
            resolved = (f.parent / rel).resolve()
            if not resolved.exists():
                errors.append(PackError(
                    file=str(f.relative_to(pack_root)),
                    field="link",
                    problem=f"reference to {target!r} does not resolve",
                    fix=f"create {rel} or fix the link target",
                ))


def _load_manifest(pack_root: Path, errors: list[PackError]) -> dict | None:
    manifest = pack_root / MANIFEST_NAME
    if not manifest.is_file():
        errors.append(PackError(
            file=MANIFEST_NAME, field="(missing)",
            problem="no manifest at the project root",
            fix=f"add exactly one {MANIFEST_NAME} at {pack_root.name}/ (FR-001)",
        ))
        return None
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(PackError(
            file=MANIFEST_NAME, field="(yaml)",
            problem=f"manifest is not parseable YAML: {exc}",
            fix="fix the YAML syntax so the manifest parses (FR-001)",
        ))
        return None
    if not isinstance(data, dict):
        errors.append(PackError(
            file=MANIFEST_NAME, field="(root)",
            problem="manifest top level is not a YAML mapping",
            fix="the manifest must be a mapping of the closed field set (FR-002)",
        ))
        return None
    return data


def _validate_manifest(pack_root: Path, data: dict, result: PipelineResult, errors: list[PackError]) -> None:

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in data or data.get(key) in (None, ""):
            errors.append(PackError(
                file=MANIFEST_NAME, field=key,
                problem=f"required manifest key {key!r} is missing or empty",
                fix=f"declare {key!r} (see docs/specs/PROJECT-OS-PACK.md §3.1) — FR-002",
            ))

    for key in data:
        if key not in KNOWN_MANIFEST_KEYS:
            result.warnings.append(
                f"{MANIFEST_NAME}: unknown top-level key {key!r} (closed field set — "
                "surfaced, not dropped; extending the set needs a spec revision + ADR, FR-004)"
            )

    name = data.get("name")
    if isinstance(name, str) and name.strip():
        if name.strip() != pack_root.name:
            errors.append(PackError(
                file=MANIFEST_NAME, field="name",
                problem=f"manifest name {name!r} != project folder segment {pack_root.name!r}",
                fix=f"set name: {pack_root.name} to match the folder (FR-003)",
            ))
        elif not _KEBAB_RE.match(name.strip()):
            errors.append(PackError(
                file=MANIFEST_NAME, field="name",
                problem=f"name {name!r} is not a kebab-case slug",
                fix="use a lowercase kebab-case slug (e.g. acme-helpdesk) — FR-003",
            ))

    constraints = data.get("constraints")
    if isinstance(constraints, list):
        for c in constraints:
            if isinstance(c, str) and _RELAX_VERB_RE.search(c) and _ORG_LAW_NOUN_RE.search(c):
                errors.append(PackError(
                    file=MANIFEST_NAME, field="constraints",
                    problem=f"constraint attempts to RELAX org law: {c.strip()[:90]!r}",
                    fix="a project-local constraint may only TIGHTEN org law, never relax it; "
                        "org law wins on conflict (FR-009 / D-6). Remove or restate as a tightening.",
                ))


def _validate_doctree(pack_root: Path, errors: list[PackError]) -> None:

    docs = pack_root / "docs"
    if not docs.is_dir():
        errors.append(PackError(
            file="docs/", field="(missing)",
            problem="no docs/ lifecycle skeleton",
            fix="scaffold the canonical docs/01-planning … docs/06-maintenance tree (FR-005)",
        ))
        return
    present = {p.name for p in docs.iterdir() if p.is_dir()}
    for canon in CANONICAL_STAGE_DIRS:
        if canon not in present:
            errors.append(PackError(
                file=f"docs/{canon}/", field="(missing)",
                problem=f"canonical AADL stage folder docs/{canon}/ is missing",
                fix=f"create docs/{canon}/ (the six-stage skeleton is exact and ordered) — FR-005",
            ))
    for extra in sorted(present - set(CANONICAL_STAGE_DIRS)):
        errors.append(PackError(
            file=f"docs/{extra}/", field="doc-tree",
            problem=f"non-canonical doc-tree folder docs/{extra}/ "
                    "(e.g. a divergent 01-intake/02-prd/… layout is NOT the contract)",
            fix="a NEW pack must use the exact canonical names "
                "01-planning/02-design/03-development/04-testing/05-deployment/06-maintenance (FR-005)",
        ))


def validate_pack(pack_root: Path, result: PipelineResult) -> bool:
    errors: list[PackError] = []
    data = _load_manifest(pack_root, errors)
    if data is not None:
        _validate_manifest(pack_root, data, result, errors)
    _validate_doctree(pack_root, errors)
    _lint_placeholders(pack_root, errors)
    _lint_links(pack_root, errors)
    result.errors.extend(errors)
    ok = not errors
    result._stage("validate", ok, "pack well-formed" if ok else f"{len(errors)} defect(s)")
    return ok


def check_discovery_gate(pack_root: Path, result: PipelineResult) -> bool:
    discovery = pack_root / DISCOVERY_REL
    text = discovery.read_text(encoding="utf-8", errors="ignore") if discovery.is_file() else ""
    if _WAIVER_RE.search(text):
        result._stage("discovery-gate", True, "explicit Founder waiver present")
        return True
    n_q, n_a = len(_Q_RE.findall(text)), len(_A_RE.findall(text))
    pairs = min(n_q, n_a)
    if pairs >= 10:
        result._stage("discovery-gate", True, f"{pairs} Q&A pairs present (>=10)")
        return True

    result.questions = list(DISCOVERY_QUESTIONS)
    result._stage(
        "discovery-gate", False,
        f"OPEN: only {pairs} Q&A pair(s) in {DISCOVERY_REL} and no waiver — "
        f"generated {len(result.questions)} discovery question(s) for the Founder",
    )
    return False


_RESEARCH_SECTIONS = (
    "Market", "Competitors", "Regulatory / Compliance", "Technical architecture",
    "Pricing / Unit economics", "SEO / Channel", "Risks",
)


def emit_research_enrichment(pack_root: Path, result: PipelineResult) -> Path:
    out = pack_root / RESEARCH_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Research enrichment — sourced conclusion for {pack_root.name}",
        "",
        "> Emitted by the WS7 gateway (scripts/gateway_compile.py, stage 3). This",
        "> sourced conclusion is stored ONLY in the project folder (QONUN Project",
        "> Placement Law). Each section requires cited primary sources before the",
        "> conclusion is treated as complete.",
        "",
    ]
    for sec in _RESEARCH_SECTIONS:
        lines += [f"## {sec}", "", "- conclusion: (fill from cited research)", "- sources: (primary source links)", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    result.research_path = out
    result._stage("research-enrichment", True, f"sourced-conclusion scaffold emitted at {RESEARCH_REL}")
    return out


def check_approved(pack_root: Path, projects_dir: Path, result: PipelineResult) -> bool:
    queue = pack_root / QUEUE_NAME
    if not queue.is_file():
        result.errors.append(PackError(
            file=QUEUE_NAME, field="(missing)",
            problem="pack carries no APPROVED-GOAL-QUEUE.md",
            fix=f"add {QUEUE_NAME} at the project root (FR-007)",
        ))
        result._stage("approved-check", False, "queue missing")
        return False

    approved = approved_queue._queue_approved(projects_dir, pack_root.name)
    if not approved:
        result.errors.append(PackError(
            file=QUEUE_NAME, field="approval-signal",
            problem="goal queue is not Founder-approved (no APPROVED: / TASDIQLANDI: / founder_approved marker)",
            fix="the Founder must approve the queue before any story ticket is compiled (FR-007 / QONUN-3)",
        ))
        result._stage("approved-check", False, "queue present but NOT Founder-approved")
        return False
    result._stage("approved-check", True, "Founder approval signal verified (check_approved_goal_queue)")
    return True


def parse_goal_queue(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    header_idx = next(
        (i for i, ln in enumerate(lines) if "|" in ln and "goal_slug" in ln.lower()),
        None,
    )
    if header_idx is None:
        return []

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    headers = [h.lower() for h in cells(lines[header_idx])]
    items: list[dict[str, str]] = []
    for ln in lines[header_idx + 1:]:
        if "|" not in ln:
            break
        row = cells(ln)
        if len(row) != len(headers) or set("".join(row)) <= set("-: "):
            continue
        rec = dict(zip(headers, row, strict=True))
        if rec.get("status", "").lower() in COMPILABLE_QUEUE_STATUSES and rec.get("goal_slug"):
            items.append(rec)
    return items


def _next_ticket_id(board_dir: Path) -> int:
    ids = [
        int(m.group(1))
        for p in board_dir.glob("DAS-*.md")
        if (m := re.match(r"DAS-(\d+)", p.name))
    ]
    return (max(ids) + 1) if ids else 1001


def _mission_excerpt(manifest: dict, limit: int = 280) -> str:
    mission = str(manifest.get("mission", "")).strip().replace("\n", " ")
    return (mission[:limit] + "…") if len(mission) > limit else mission


ORG_PATH = ROOT / "config" / "org.yaml"
FALLBACK_DEPT = "engineering"


def role_departments(org_path: Path | None = None) -> dict[str, str]:
    path = org_path or ORG_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        return {}
    return {
        str(spec["key"]).strip(): str(spec["dept"]).strip()
        for spec in roles
        if isinstance(spec, dict) and str(spec.get("key", "")).strip()
        and str(spec.get("dept", "")).strip()
    }


def _write_ticket(board_dir: Path, tid: int, *, slug: str, title: str, status: str,
                  assignee: str, dept: str, parent: str, goal: str, stage_tag: str, gate: str,
                  body: str) -> Path:
    today = date.today().isoformat()
    fm = [
        "---",
        f"id: DAS-{tid}",
        f"title: {title}",
        f"status: {status}",
        f"assignee: {assignee}",
        "author: ceo",
        f"dept: {dept or FALLBACK_DEPT}",
        "priority: p1",
        f"parent: {parent}" if parent else "parent:",
        f"goal: {goal}",
        f"project: {slug}",
        f"stage: {gate}" if gate else "",
        f"created: {today}",
        f"updated: {today}",
        "---",
        "",
    ]
    fm = [ln for ln in fm if ln != ""]
    if not body.endswith("\n"):
        body += "\n"
    path = board_dir / f"DAS-{tid}-{goal}-{stage_tag}.md"
    path.write_text("\n".join(fm) + "\n" + body, encoding="utf-8")
    return path


def compile_story_tickets(pack_root: Path, manifest: dict, result: PipelineResult) -> list[Path]:
    queue_text = (pack_root / QUEUE_NAME).read_text(encoding="utf-8", errors="ignore")
    goals = parse_goal_queue(queue_text)
    if not goals:
        result.errors.append(PackError(
            file=QUEUE_NAME, field="goal-items",
            problem="queue is Founder-approved but has no founder_approved/planned/active goal item to compile",
            fix="add at least one prioritized goal row with status: founder_approved (see /daslab-plan queue schema)",
        ))
        result._stage("compile", False, "no compilable goal item")
        return []

    board_dir = pack_root / "board-tickets"
    board_dir.mkdir(parents=True, exist_ok=True)
    depts = role_departments()
    slug = pack_root.name
    mission = _mission_excerpt(manifest)
    written: list[Path] = []
    tid = _next_ticket_id(board_dir)

    for goal in goals:
        goal_slug = goal["goal_slug"]
        outcome = goal.get("outcome", "").strip() or "(outcome not specified in queue)"
        owner = goal.get("owner", "").strip() or "cpo"
        if owner not in {r for _n, _nm, _g, _d, r, _a in AADL_STAGES} | {
            "cpo", "cto", "ceo", "qa-lead", "sre-lead", "coo", "senior-pm",
        }:
            owner = "cpo"


        epic_id = tid
        tid += 1
        epic_body = (
            f"## Description\n\n"
            f"**Epic — {goal_slug}** (AI-agent lifecycle, all six AADL stages).\n\n"
            f"**Embedded context (from {slug}/PROJECT-OS.yaml).** {mission}\n\n"
            f"**Goal outcome.** {outcome}\n\n"
            f"Compiled by the WS7 gateway from a Founder-approved PROJECT-OS-PACK. "
            f"Child tickets are one-per-AADL-stage; each is self-contained.\n\n"
            f"## Acceptance criteria\n\n"
            f"- [ ] all six stage children reach `done` behind their AADL gate\n"
            f"- [ ] GATE-1…GATE-6 signed in {slug}/README.md stage board\n"
        )
        epic_path = _write_ticket(
            board_dir, epic_id, slug=slug, title=f"{goal_slug} — epic", status="backlog",
            assignee=owner, dept=depts.get(owner, FALLBACK_DEPT), parent="",
            goal=goal_slug, stage_tag="epic", gate="",
            body=epic_body,
        )
        written.append(epic_path)

        prev_stage_id: int | None = None
        for stage_no, stage_name, gate, doc_dir, role, gate_seed in AADL_STAGES:
            sid = tid
            tid += 1
            produces = f"{doc_dir}/ artifacts + {gate} sign-off"
            consumes = (
                "PROJECT-OS.yaml manifest + Founder discovery answers"
                if prev_stage_id is None
                else f"DAS-{prev_stage_id} (Stage {stage_no - 1}) outputs"
            )
            body = (
                f"## Description\n\n"
                f"**Stage {stage_no} — {stage_name}** story ticket for `{goal_slug}` "
                f"(project `{slug}`).\n\n"
                f"**Embedded context (zero-archaeology).** Mission: {mission}\n\n"
                f"Goal outcome: {outcome}\n\n"
                f"This ticket delivers the AADL Stage-{stage_no} mandatory artifacts in "
                f"`docs/{doc_dir}/` and closes **{gate}**. It was compiled from the "
                f"Founder-approved goal queue — no hand-written archaeology needed.\n\n"
                f"## Acceptance criteria\n\n"
                f"- [ ] Stage-{stage_no} artifacts authored in `docs/{doc_dir}/`\n"
                f"- [ ] {gate}: {gate_seed}\n"
                f"- [ ] stage board in `{slug}/README.md` updated with the {gate} result\n\n"
                f"## Produces / Consumes\n\n"
                f"- **produces:** {produces}\n"
                f"- **consumes:** {consumes}\n\n"
                f"## Gate reference\n\n"
                f"- AADL stage: **Stage {stage_no} — {stage_name}**\n"
                f"- Gate: **{gate}** (governance/policies/ai-agent-lifecycle.md §3)\n"
            )
            spath = _write_ticket(
                board_dir, sid, slug=slug, title=f"{goal_slug} — Stage {stage_no}: {stage_name}",
                status="todo", assignee=role, dept=depts.get(role, FALLBACK_DEPT),
                parent=f"DAS-{epic_id}", goal=goal_slug,
                stage_tag=f"s{stage_no}-{doc_dir}", gate=gate, body=body,
            )
            written.append(spath)
            prev_stage_id = sid

    result.tickets = written
    result._stage("compile", True, f"{len(written)} story ticket(s) → {board_dir.relative_to(pack_root.parent)}")
    return written


def run_pipeline(pack_root: Path, projects_dir: Path | None = None) -> PipelineResult:
    pack_root = pack_root.resolve()
    projects_dir = (projects_dir or pack_root.parent).resolve()
    result = PipelineResult(slug=pack_root.name)


    if not validate_pack(pack_root, result):
        result.rejected_stage = "validate"
        return result


    if not check_discovery_gate(pack_root, result):
        result.rejected_stage = "discovery-gate"
        return result


    emit_research_enrichment(pack_root, result)


    if not check_approved(pack_root, projects_dir, result):
        result.rejected_stage = "approved-check"
        return result


    manifest = yaml.safe_load((pack_root / MANIFEST_NAME).read_text(encoding="utf-8"))
    tickets = compile_story_tickets(pack_root, manifest, result)
    if not tickets:
        result.rejected_stage = "compile"
        return result

    result.ok = True
    return result


def _render(result: PipelineResult) -> str:
    out: list[str] = []
    out.append(f"GATEWAY intake — project '{result.slug}'")
    out.append("=" * 60)
    for st in result.stages:
        out.append(f"  [{'OK ' if st.ok else 'FAIL'}] {st.name}: {st.detail}")
    if result.warnings:
        out.append("\nWarnings:")
        out.extend(f"  WARN  {w}" for w in result.warnings)
    if result.errors:
        out.append(f"\nREJECTED at stage '{result.rejected_stage}' — {len(result.errors)} actionable error(s):")
        for e in result.errors:
            out.append(f"  - {e}")
    if result.questions:
        out.append("\nDiscovery gate is OPEN — take these questions to the Founder:")
        out.extend(f"  Q{i}. {q}" for i, q in enumerate(result.questions, start=1))
    if result.research_path:
        out.append(f"\nResearch-enrichment step emitted: {result.research_path}")
    if result.ok:
        out.append(f"\nCOMPILED {len(result.tickets)} story ticket(s):")
        out.extend(f"  + {p.name}" for p in result.tickets)
    return "\n".join(out)


def _as_dict(result: PipelineResult) -> dict:
    return {
        "slug": result.slug,
        "ok": result.ok,
        "rejected_stage": result.rejected_stage,
        "stages": [{"name": s.name, "ok": s.ok, "detail": s.detail} for s in result.stages],
        "errors": [e.__dict__ for e in result.errors],
        "warnings": result.warnings,
        "questions": result.questions,
        "research_path": str(result.research_path) if result.research_path else None,
        "tickets": [str(p) for p in result.tickets],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='gateway_compile.py — ORGANISM WS7 GATEWAY intake pipeline (O7-T02, P22)', formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack_root", help="the project folder projects/<name>/ to compile")
    ap.add_argument("--projects-dir", default=None,
                    help="the projects/ root (default: parent of pack_root) — for the approved-queue gate")
    ap.add_argument("--gate-walk", action="store_true",
                    help="do NOT compile: walk the AADL gate order over <pack-root>/board-tickets/ "
                         "and refuse to advance past an open gate (P22 / stage-gated delivery)")
    ap.add_argument("--emit-cards", action="store_true",
                    help="with --gate-walk: emit gate interrupt-cards to board/interrupts/ (DAS-1446)")
    ap.add_argument("--interrupts", default=None,
                    help="with --emit-cards: interrupt-card output dir (default: board/interrupts/)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    pack_root = Path(args.pack_root)
    if not pack_root.is_dir():
        print(f"ERROR: pack root not found: {pack_root}", file=sys.stderr)
        return 2
    projects_dir = Path(args.projects_dir) if args.projects_dir else None


    if args.gate_walk:
        import stage_gate
        board = pack_root / "board-tickets"
        if not board.is_dir():
            print(f"ERROR: no board-tickets/ under {pack_root} — compile the pack first",
                  file=sys.stderr)
            return 2
        walk = stage_gate.walk_gates(board)
        if args.emit_cards:
            interrupts = (Path(args.interrupts) if args.interrupts
                          else stage_gate.ROOT / "board" / "interrupts")
            stage_gate.emit_gate_cards(walk, interrupts)
        if args.json:
            print(json.dumps(stage_gate._as_dict(walk), indent=2))
        else:
            print(stage_gate.render_walk(walk))
        return 0 if walk.ok else 1

    result = run_pipeline(pack_root, projects_dir)
    if args.json:
        print(json.dumps(_as_dict(result), indent=2))
    else:
        print(_render(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
