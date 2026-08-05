#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_heartbeat_readiness as hr
import feature_flags
import kill_switch_drill as ksd
import loop_controller as lc
from _paths import ROOT

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


GO = "GO"
NO_GO = "NO-GO"

DEFAULT_HISTORY = ROOT / "board" / ".metrics-history.jsonl"
DEFAULT_EVENTS = ROOT / "board" / ".events.jsonl"
DEFAULT_BUDGETS = ROOT / "config" / "budgets.yaml"
DEFAULT_LOOP_CONFIG = ROOT / "config" / "loop.yaml"
DEFAULT_BOARD = ROOT / "board"
DEFAULT_INTERRUPTS = ROOT / "board" / "interrupts"
DEFAULT_TAXONOMY = ROOT / "config" / "risk_taxonomy.yaml"
DEFAULT_FEATURES = ROOT / "config" / "features.yaml"
DAEMON_SCAN_TEST = ROOT / "tests" / "test_no_daemon.py"


THE_FLIP = "config/features.yaml:  heartbeat_enabled: false  ->  true"


@dataclass(frozen=True)
class Check:

    key: str
    si: str
    title: str
    state: str
    detail: str
    source: str
    gating: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "si": self.si,
            "title": self.title,
            "state": self.state,
            "detail": self.detail,
            "source": self.source,
            "gating": self.gating,
        }


def _unknown(key: str, si: str, title: str, why: str, source: str) -> Check:
    return Check(key, si, title, UNKNOWN, why, source)


def probe_flag(features_path: Path) -> Check:
    try:
        if not features_path.is_file():
            return _unknown(
                "flag_state", "SI-7", "heartbeat_enabled is still OFF",
                f"COULD NOT CHECK — feature-flag file absent: {_rel(features_path)}",
                _rel(features_path),
            )
        on = bool(feature_flags.enabled("heartbeat_enabled", features_path))
    except Exception as exc:
        return _unknown("flag_state", "SI-7", "heartbeat_enabled is still OFF",
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", _rel(features_path))
    if on:
        return Check("flag_state", "SI-7", "heartbeat_enabled is still OFF", FAIL,
                     "heartbeat_enabled is ALREADY true — the org is live; "
                     "there is no pre-flip decision left to gate",
                     _rel(features_path))
    return Check("flag_state", "SI-7", "heartbeat_enabled is still OFF", PASS,
                 "false (shadow) — the flip has not been made", _rel(features_path))


def probe_readiness(history_path: Path, budgets_path: Path, events_path: Path,
                    features_path: Path) -> tuple[Check, Check, dict[str, Any]]:
    win_title = "clean shadow window >= 3 days"
    cred_title = "monthly credit ceiling enforceable (FR-004)"
    try:
        history = lc._load_jsonl(history_path)
        flag_on = bool(feature_flags.enabled("heartbeat_enabled", features_path))
        active_plan = hr._active_plan(budgets_path)
        credit_exhausted = (
            lc._monthly_credit_exhausted(budgets_path, events_path) if active_plan else False
        )
        report = hr.assess(history, flag_on, active_plan=active_plan,
                           credit_exhausted=credit_exhausted)
    except Exception as exc:
        why = f"COULD NOT CHECK — {type(exc).__name__}: {exc}"
        return (
            _unknown("shadow_window", "SI-7", win_title, why, _rel(history_path)),
            _unknown("credit_ceiling", "SI-5/FR-004", cred_title, why, _rel(budgets_path)),
            {},
        )


    src_note = "" if history_path.is_file() else "  [evidence file ABSENT]"
    window = Check(
        "shadow_window", "SI-7", win_title,
        PASS if report["window_met"] else FAIL,
        f"{report['clean_days']}/{report['clean_days_required']} consecutive clean day(s) "
        f"from {report['history_rows']} history row(s){src_note}",
        _rel(history_path),
    )


    if not budgets_path.is_file():
        credit = _unknown("credit_ceiling", "SI-5/FR-004", cred_title,
                          f"COULD NOT CHECK — budgets file absent: {_rel(budgets_path)}",
                          _rel(budgets_path))
    else:
        plan = report["active_plan"] or "undeclared"
        ok = report["credit_ceiling_enforceable"] and not report["credit_exhausted"]
        credit = Check(
            "credit_ceiling", "SI-5/FR-004", cred_title,
            PASS if ok else FAIL,
            f"mustaqil.monthly_credit_ceiling: active_plan={plan}, "
            f"exhausted={report['credit_exhausted']}"
            + ("" if report["credit_ceiling_enforceable"]
               else " — an undeclared active_plan makes the outer ceiling unenforceable"),
            f"{_rel(budgets_path)} :: mustaqil.monthly_credit_ceiling",
        )
    return window, credit, report


def _si5_cap_note(budgets_path: Path) -> str:
    try:
        import ws_b_admission

        mustaqil = ws_b_admission.load_mustaqil_budgets(budgets_path)
        caps = (mustaqil or {}).get("caps") or {}
        run = (caps.get("per_run") or {}).get("max_cost_usd", "__absent__")
        day = (caps.get("per_day") or {}).get("max_cost_usd", "__absent__")
    except Exception:
        return "SI-5 caps: UNREADABLE"
    def fmt(value: Any) -> str:
        return "MISSING" if value == "__absent__" else f"${value}"

    return f"SI-5 caps: per_run={fmt(run)}/run, per_day={fmt(day)}/day"


def probe_credit_ceiling_shape(budgets_path: Path) -> Check:
    title = "credit exhaustion resolves to a sanctioned pause, not a false-green"
    src = (f"{_rel(budgets_path)} :: mustaqil  "
           "(owner: scripts/ws_b_health_check.py :: check_budget_ceiling_drift)")
    if not budgets_path.is_file():
        return _unknown("credit_semantics", "SI-5/FR-004", title,
                        f"COULD NOT CHECK — budgets file absent: {_rel(budgets_path)}", src)
    try:
        import ws_b_health_check

        result = ws_b_health_check.check_budget_ceiling_drift(budgets_path)
    except Exception as exc:
        return _unknown("credit_semantics", "SI-5/FR-004", title,
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", src)
    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
        return _unknown("credit_semantics", "SI-5/FR-004", title,
                        "COULD NOT CHECK — the owning drift checker returned no verdict", src)
    detail = str(result.get("detail") or "").strip() or "no detail reported"
    return Check("credit_semantics", "SI-5/FR-004", title,
                 PASS if result["ok"] else FAIL,
                 f"{detail} — {_si5_cap_note(budgets_path)}", src)


def probe_kill_switch_drill(*, skip: bool = False) -> Check:
    title = "kill-switch + safety-rail drill (6 rails)"
    src = "scripts/kill_switch_drill.py --smoke"
    if skip:
        return _unknown("kill_switch_drill", "SI-3..SI-7", title,
                        "COULD NOT CHECK — skipped by operator (--skip-drill)", src)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = ksd.main(["--smoke"])
    except Exception as exc:
        return _unknown("kill_switch_drill", "SI-3..SI-7", title,
                        f"COULD NOT CHECK — drill raised {type(exc).__name__}: {exc}", src)
    rails = next((ln.split(":", 1)[-1].strip()
                  for ln in buf.getvalue().splitlines() if "pass[" in ln), "")
    if rc == 2:
        return _unknown("kill_switch_drill", "SI-3..SI-7", title,
                        "COULD NOT CHECK — drill usage error", src)
    if not rails:

        return _unknown("kill_switch_drill", "SI-3..SI-7", title,
                        "COULD NOT CHECK — drill produced no per-rail result line", src)
    return Check("kill_switch_drill", "SI-3..SI-7", title,
                 PASS if rc == 0 else FAIL, rails, src)


def probe_loop_mode(loop_config: Path) -> Check:
    title = "self-optimizing loop stays OFF"
    src = "scripts/check_loop_mode.py"
    try:
        import check_loop_mode

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = check_loop_mode.main(["--config", str(loop_config)])
    except Exception as exc:
        return _unknown("loop_mode", "SI-2", title,
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", src)
    out = buf.getvalue().strip().splitlines()
    detail = out[-1] if out else f"exit {rc}"
    if rc == 2:


        return _unknown("loop_mode", "SI-2", title, f"COULD NOT CHECK — {detail}", src)
    return Check("loop_mode", "SI-2", title, PASS if rc == 0 else FAIL, detail, src)


_CHECKED_RE = re.compile(r"OK:\s*(\d+)\s+tickets checked")


def probe_never_auto_approve(board: Path, taxonomy: Path) -> Check:
    title = "never-auto-approve violations on the board"
    src = "scripts/check_never_auto_approve.py"
    try:
        import check_never_auto_approve as naa

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = naa.main(["--board", str(board), "--config", str(taxonomy)])
    except Exception as exc:
        return _unknown("never_auto_approve", "SI-7", title,
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", src)
    text = buf.getvalue().strip()
    if rc == 2:
        return _unknown("never_auto_approve", "SI-7", title,
                        f"COULD NOT CHECK — {text.splitlines()[-1] if text else 'usage error'}",
                        src)
    m = _CHECKED_RE.search(text)
    if rc == 0 and m:
        return Check("never_auto_approve", "SI-7", title, PASS,
                     f"0 violations across {m.group(1)} ticket(s) checked", src)
    if rc == 0:


        return _unknown("never_auto_approve", "SI-7", title,
                        "COULD NOT CHECK — checker returned 0 but reported no ticket count", src)
    last = text.strip().splitlines()[-1] if text.strip() else "violations reported"
    return Check("never_auto_approve", "SI-7", title, FAIL, last, src)


def probe_event_log_violations(events_path: Path) -> Check:
    title = "zero auto-approved gate/interrupt events in the event log"
    src = _rel(events_path)
    if not events_path.is_file():
        return _unknown("event_log", "SI-7", title,
                        f"COULD NOT CHECK — event log ABSENT ({src}); 0 events scanned is "
                        "NOT evidence of 0 violations", src)
    try:
        events = lc._load_jsonl(events_path)
    except Exception as exc:
        return _unknown("event_log", "SI-7", title,
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", src)
    if not events:
        return _unknown("event_log", "SI-7", title,
                        f"COULD NOT CHECK — event log present but EMPTY ({src}); "
                        "0 events scanned is NOT evidence of 0 violations", src)
    violations = ksd.scan_gate_approval_violations(events)
    if violations:
        return Check("event_log", "SI-7", title, FAIL,
                     f"{len(violations)} auto-approved gate/approval event(s) "
                     f"across {len(events)} event(s)", src)
    return Check("event_log", "SI-7", title, PASS,
                 f"0 violations across {len(events)} event(s) scanned", src)


def probe_interrupt_cards(interrupts_dir: Path) -> Check:
    title = "no interrupt-card awaiting a Founder answer"
    src = _rel(interrupts_dir)
    if not interrupts_dir.is_dir():
        return _unknown("interrupt_cards", "SI-7", title,
                        f"COULD NOT CHECK — interrupt-card store absent ({src})", src)
    open_cards: list[str] = []
    total = 0
    for card in sorted(interrupts_dir.glob("*.json")):
        try:
            data = json.loads(card.read_text(encoding="utf-8"))
        except Exception:
            total += 1
            open_cards.append(f"{card.name} (unreadable)")
            continue
        if not (isinstance(data, dict) and "question" in data):
            continue
        total += 1
        answer = data.get("resume")
        if not (isinstance(answer, str) and answer.strip()):
            open_cards.append(card.name)
    if open_cards:
        return Check("interrupt_cards", "SI-7", title, FAIL,
                     f"{len(open_cards)} of {total} card(s) unanswered: "
                     + ", ".join(open_cards[:5]), src)
    return Check("interrupt_cards", "SI-7", title, PASS,
                 f"all {total} card(s) carry a Founder answer", src)


def probe_no_daemon(*, skip: bool = False) -> Check:
    title = "scheduler is one-shot, not a daemon (in-repo half)"
    src = "tests/test_no_daemon.py"
    if skip:
        return _unknown("no_daemon", "SI-1", title,
                        "COULD NOT CHECK — skipped by operator (--skip-daemon-scan)", src)
    if not DAEMON_SCAN_TEST.is_file():
        return _unknown("no_daemon", "SI-1", title,
                        f"COULD NOT CHECK — scanner absent: {src}", src)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(DAEMON_SCAN_TEST), "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=300, check=False,
        )
    except Exception as exc:
        return _unknown("no_daemon", "SI-1", title,
                        f"COULD NOT CHECK — {type(exc).__name__}: {exc}", src)
    tail = [ln.strip(" =").strip() for ln in proc.stdout.strip().splitlines() if ln.strip(" =").strip()]
    detail = tail[-1] if tail else f"exit {proc.returncode}"
    return Check("no_daemon", "SI-1", title,
                 PASS if proc.returncode == 0 else FAIL, detail, src)


def context_lines(history_path: Path, events_path: Path, loop_config: Path) -> list[Check]:
    out: list[Check] = []


    try:
        history = lc._load_jsonl(history_path)
        mode = str(lc._load_yaml(loop_config).get("mode") or "unknown")
        ladder_streak = lc.clean_live_days(history, lc.DEFAULT_TARGETS)
        out.append(Check(
            "ladder_clock", "SI-2", "loop-promotion ladder clock (a DIFFERENT clock)",
            PASS if ladder_streak >= lc.MIN_CLEAN_DAYS else FAIL,
            f"{ladder_streak}/{lc.MIN_CLEAN_DAYS} clean day(s) on the FULL T1-T5+T7 bar, "
            f"loop mode='{mode}' — gates config/loop.yaml only; it does NOT gate "
            "heartbeat_enabled and is NOT a blocker for this decision",
            "scripts/loop_controller.py (MIN_CLEAN_DAYS=7) + a human-approved GATE-6 record",
            gating=False,
        ))
    except Exception as exc:
        out.append(Check("ladder_clock", "SI-2", "loop-promotion ladder clock (a DIFFERENT clock)",
                         UNKNOWN, f"COULD NOT CHECK — {type(exc).__name__}: {exc}",
                         "scripts/loop_controller.py", gating=False))


    if not events_path.is_file():
        out.append(Check("rolling_waves", "—", "release criterion: >= 7 rolling waves",
                         UNKNOWN,
                         f"COULD NOT CHECK — event log ABSENT ({_rel(events_path)}); "
                         "counts WAVES not days, gates a VERSION bump only, authorizes "
                         "no autonomy — NOT a blocker for this decision",
                         _rel(events_path), gating=False))
    else:
        try:
            events = lc._load_jsonl(events_path)
            waves = sum(1 for e in events if str(e.get("event_type") or "") == "run_end")
            out.append(Check("rolling_waves", "—", "release criterion: >= 7 rolling waves",
                             PASS if waves >= 7 else FAIL,
                             f"{waves}/7 completed wave(s) in the event log — counts WAVES "
                             "not days, gates a VERSION bump only, authorizes no autonomy "
                             "— NOT a blocker for this decision",
                             _rel(events_path), gating=False))
        except Exception as exc:
            out.append(Check("rolling_waves", "—", "release criterion: >= 7 rolling waves",
                             UNKNOWN, f"COULD NOT CHECK — {type(exc).__name__}: {exc}",
                             _rel(events_path), gating=False))


    out.append(Check(
        "os_scheduler", "SI-1", "OS scheduler entry (external half)", UNKNOWN,
        "COVERED-BY-CONSTRUCTION — the cadence lives in a Founder-owned launchd/cron "
        "entry this repo documents and deliberately never installs "
        "(board/schedule.yaml: installed: false). No repo-side check is possible and "
        "none is to be invented (design §5)",
        "board/schedule.yaml", gating=False,
    ))
    return out


def collect(
    *,
    history: Path = DEFAULT_HISTORY,
    events: Path = DEFAULT_EVENTS,
    budgets: Path = DEFAULT_BUDGETS,
    loop_config: Path = DEFAULT_LOOP_CONFIG,
    board: Path = DEFAULT_BOARD,
    interrupts: Path = DEFAULT_INTERRUPTS,
    taxonomy: Path = DEFAULT_TAXONOMY,
    features: Path = DEFAULT_FEATURES,
    skip_drill: bool = False,
    skip_daemon_scan: bool = False,
) -> tuple[list[Check], list[Check], dict[str, Any]]:
    window, credit, raw = probe_readiness(history, budgets, events, features)
    gating = [
        probe_flag(features),
        window,
        credit,
        probe_credit_ceiling_shape(budgets),
        probe_kill_switch_drill(skip=skip_drill),
        probe_loop_mode(loop_config),
        probe_never_auto_approve(board, taxonomy),
        probe_event_log_violations(events),
        probe_interrupt_cards(interrupts),
        probe_no_daemon(skip=skip_daemon_scan),
    ]
    return gating, context_lines(history, events, loop_config), raw


def verdict(gating: list[Check]) -> dict[str, Any]:
    failed = [c for c in gating if c.state == FAIL]

    unknown = [c for c in gating if c.state not in (PASS, FAIL)]
    go = bool(gating) and all(c.state == PASS for c in gating)
    return {
        "verdict": GO if go else NO_GO,
        "go": go,
        "checked_and_failing": [c.key for c in failed],
        "could_not_check": [c.key for c in unknown],
        "checked_and_clean": [c.key for c in gating if c.state == PASS],
    }


def build_report(**kwargs: Any) -> dict[str, Any]:
    gating, context, raw = collect(**kwargs)
    v = verdict(gating)
    return {
        "verdict": v["verdict"],
        "go": v["go"],
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "the_founder_act": THE_FLIP,
        "is_a_recommendation": False,
        "summary": v,
        "gates": [c.as_dict() for c in gating],
        "context": [c.as_dict() for c in context],
        "readiness_reporter": raw,
    }


_W = 78


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except (ValueError, OSError):
        return str(path)


def _wrap(text: str, indent: int, width: int = _W) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width=width - indent) or [""]


def _para(text: str, indent: int, *, hang: int | None = None) -> list[str]:
    lines = _wrap(text, indent)
    hang_n = indent if hang is None else hang
    return [" " * indent + lines[0]] + [" " * hang_n + ln for ln in lines[1:]]


def _block(state: str, title: str, detail: str, si: str) -> list[str]:


    label = {PASS: "PASS   ", FAIL: "FAIL   ", UNKNOWN: "UNKNOWN"}.get(state, f"{state[:7]:<7}")
    lines = [f"  [{label}] {title}  ({si})"]
    lines += [f"            {ln}" for ln in _wrap(detail, 12)]
    return lines


def render(report: dict[str, Any]) -> str:
    go = report["go"]
    gates = [Check(**g) for g in report["gates"]]
    context = [Check(**c) for c in report["context"]]
    s = report["summary"]

    out: list[str] = []
    out.append("=" * _W)
    out.append("HEARTBEAT GO / NO-GO — Founder readiness report")
    out.append("ADR-0027 SI-1..SI-7 · SPEC-010 · read-only evidence, composed from the")
    out.append("existing checks. This report decides nothing new and can flip nothing.")
    out.append("=" * _W)
    out.append("")
    out.append(f"   VERDICT:  {report['verdict']}")
    out.append("")
    if go:
        out += _para(
            "Every gate below was checked against real evidence and is clean. That "
            "means the evidence bar is met — it is NOT a recommendation to flip, and "
            "this report does not advise for or against the decision.", 3)
    else:
        n_fail = len(s["checked_and_failing"])
        n_unk = len(s["could_not_check"])
        out += _para(
            f"NOT READY. {n_fail} gate(s) checked and failing; {n_unk} gate(s) could "
            "not be checked at all. A gate that could not be checked is not a pass: "
            "the evidence for it does not exist yet.", 3)
    out.append("")
    out.append("-" * _W)
    out.append("THE DECISION THIS REPORT INFORMS")
    out.append("-" * _W)
    out.append("  One edit, made by the Founder alone:")
    out.append(f"      {report['the_founder_act']}")
    out += _para(
        "No agent may make that edit (QONUN-5 never-auto-approve / ADR-0027 SI-7 / "
        "SPEC-010 FR-006). This tool has no code path that writes any config file; "
        "it reports evidence and stops there.", 2)
    out.append("")

    out.append("-" * _W)
    out.append("HOW TO READ A STATE")
    out.append("-" * _W)
    out.append("  PASS      checked against real evidence, and clean")
    out.append("  FAIL      checked against real evidence, and failing")
    out.append("  UNKNOWN   COULD NOT CHECK — the evidence source is absent or empty,")
    out.append("            or the check could not run. UNKNOWN is never a pass and")
    out.append("            always blocks GO. A missing input reads as NOT READY,")
    out.append("            never as 'no issues found'.")
    out.append("")

    out.append("-" * _W)
    out.append("GATES — all of these must be PASS")
    out.append("-" * _W)
    for c in gates:
        out += _block(c.state, c.title, c.detail, c.si)
        out.append(f"            source: {c.source}")
    out.append("")

    out.append("-" * _W)
    out.append("THREE '>= N' NUMBERS — DO NOT CONFLATE THEM")
    out.append("-" * _W)
    win = next((c for c in gates if c.key == "shadow_window"), None)
    out.append("  1. >= 3 CLEAN DAYS  — the heartbeat go-live clock (SI-7).")
    out.append(f"        {win.detail if win else 'unavailable'}")
    out.append("        Gates: heartbeat_enabled. This is the ONLY clock this")
    out.append("        decision depends on.")
    for c in context:
        if c.key == "ladder_clock":
            out.append("  2. >= 7 CLEAN DAYS  — the loop-promotion LADDER clock (SI-2).")
            out += [f"        {ln}" for ln in _wrap(c.detail, 8)]
        elif c.key == "rolling_waves":
            out.append("  3. >= 7 ROLLING WAVES — a release criterion, NOT a clock.")
            out += [f"        {ln}" for ln in _wrap(c.detail, 8)]
    out.append("")

    out.append("-" * _W)
    out.append("SI-1..SI-7 EVIDENCE MAP — per-invariant, no single aggregate")
    out.append("-" * _W)
    for si in ("SI-1", "SI-2", "SI-3..SI-7", "SI-5/FR-004", "SI-7", "—"):
        rows = [c for c in [*gates, *context] if c.si == si]
        if not rows:
            continue
        out.append(f"  {si}")
        for c in rows:
            gate = "gate" if c.gating else "info"
            out.append(f"    {c.state:<7} [{gate}] {c.title}")
    out.append("")

    out.append("-" * _W)
    out.append("WHAT THIS REPORT DOES NOT ESTABLISH (design ws-f-tempo-verification §2.3)")
    out.append("-" * _W)
    out += _para("- It does not establish that a clean shadow window exists; only "
                 "counted waves (merged PR + green CI + T7) move that number.", 2, hang=4)
    out += _para("- It does not verify the OS-scheduler half of SI-1; nothing in-repo "
                 "installs or inspects a launchd/cron entry, by design.", 2, hang=4)
    out += _para("- It does not approve anything. It signs no gate, answers no "
                 "interrupt-card, and cannot write to config/features.yaml.", 2, hang=4)
    out.append("")
    out.append("=" * _W)
    out.append(f"  VERDICT: {report['verdict']}"
               + ("" if go else "   — the evidence bar is NOT met today."))
    out.append("=" * _W)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='heartbeat_go_no_go.py — the ONE Founder-facing go/no-go readiness report (DAS-1619).')
    ap.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    ap.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    ap.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    ap.add_argument("--loop-config", type=Path, default=DEFAULT_LOOP_CONFIG)
    ap.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    ap.add_argument("--interrupts", type=Path, default=DEFAULT_INTERRUPTS)
    ap.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    ap.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    ap.add_argument("--skip-drill", action="store_true",
                    help="skip the kill-switch drill (its gate becomes UNKNOWN, never a pass)")
    ap.add_argument("--skip-daemon-scan", action="store_true",
                    help="skip the SI-1 daemon scan (its gate becomes UNKNOWN, never a pass)")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    report = build_report(
        history=args.history, events=args.events, budgets=args.budgets,
        loop_config=args.loop_config, board=args.board, interrupts=args.interrupts,
        taxonomy=args.taxonomy, features=args.features,
        skip_drill=args.skip_drill, skip_daemon_scan=args.skip_daemon_scan,
    )
    print(json.dumps(report, indent=2, default=str) if args.json else render(report))
    return 0 if report["go"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
