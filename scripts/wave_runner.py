"""wave_runner.py — the deterministic post-decision wave lifecycle shim (DAS-1499).

ORGANISM WS8 ATTEST — the single seam through which a wave's done-ness is
emitted, guardrailed, ledgered, evidenced, and attested.  Per **ADR-0031** the
wave LIFECYCLE MECHANICS move out of ``daslab-cycle/SKILL.md`` prose into one
deterministic entry point, :func:`run_wave`, which:

  1. opens/continues the run — a wave-boundary checkpoint (``pulse_checkpoint``),
  2. emits ``run_start`` / ``run_end`` / ``span`` per dispatch (``dispatch_emitter``),
  3. invokes per-role INPUT/OUTPUT guardrails on the collected outputs
     (``guardrail_dispatch``),
  4. writes/updates the progress-ledger + task-ledger + per-ticket completions,
     then a wave-close checkpoint (``check_ledger`` / ``task_ledger`` /
     ``pulse_checkpoint``),
  5. snapshots committed, redacted evidence per dispatch (``snapshot_evidence``),
  6. writes a COMMITTED, redacted, doubly hash-chained :class:`WaveAttestation`
     to ``metrics/attestations/<run_id>.json``,
  7. co-produces, ATOMICALLY with (6), a COMMITTED, append-only, hash-chained
     entry in the TRACKED ``board/wave-ledger.jsonl`` (**ADR-0032** §1) — a
     SECOND, independent committed chain that binds each recorded wave to its
     attestation (``attestation_hash``) so an omitted or tampered wave breaks a
     committed chain instead of leaving a silent gap.

Design invariants (ADR-0031 §2 — the load-bearing constraint)
-------------------------------------------------------------
* **No LLM, no decision inside.** ``plan`` carries the routing DECISION already
  taken by the orchestrator (which tickets, to which roles, on which models);
  ``results`` carries the collected OUTCOMES already observed.  ``run_wave`` is a
  pure orchestration of already-shipped primitives — it holds no routing logic,
  no selection guard, no model-tier choice, and reads no clock or network (every
  timestamp is caller-supplied).  Given ``(plan, results)`` it does the SAME
  mechanical steps every time.
* **flag-on == flag-off DISPATCH DECISIONS.**  The runner is ``organism_emit``-
  gated: with the flag OFF it is a no-op (writes nothing, returns ``None``) and
  the wave dispatches byte-identically; with it ON the ONLY difference is the
  post-decision artifacts it writes.  It never both READS the event store AND
  routes the normal wave, so it satisfies the ADR-0025 §(d) reader-vs-router
  shadow rule by PROPERTY — it reads its inputs from the ``plan`` / ``results``
  arguments and writes exclusively via the append-only producers, with no
  filename to add to any allowlist.
* **REUSE, never re-implement.**  Every mechanic goes through the existing
  library (``dispatch_emitter`` / ``pulse_checkpoint`` / ``guardrail_dispatch`` /
  ``task_ledger`` / ``check_ledger`` / ``snapshot_evidence``).  The runner drives
  producers; it never forks their redaction, schemas, or append-only discipline,
  and it never imports ``dgox.*`` for a read.

Public API
----------
    TicketPlan / WavePlan               # the routing DECISION (immutable input)
    TicketResult / WaveResults          # the collected OUTCOMES (immutable input)
    WaveAttestation                     # the committed receipt returned
    run_wave(plan, results, *, created_at, ...) -> WaveAttestation | None
    ATTEST_DIR                          # committed attestation dir (TRACKED)
    LEDGER_PATH / LEDGER_FIELDS         # committed wave-ledger (TRACKED, ADR-0032)
    append_wave_ledger_entry(...)       # atomic hash-chained ledger append
    attestation_path(run_id, attest_dir)
    load_attestation(path) / verify_attestation(att)
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating import of the shipped primitives (same bootstrap pattern the
# sibling scripts use — make scripts/ importable regardless of invocation).
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_ledger as _cl  # noqa: E402
import dispatch_emitter as _de  # noqa: E402
import guardrail_dispatch as _gd  # noqa: E402
import pulse_checkpoint as _pc  # noqa: E402
import snapshot_evidence as _se  # noqa: E402
import task_ledger as _tl  # noqa: E402
from _paths import ROOT  # noqa: E402
from guardrails import runner as _gr  # noqa: E402

__all__ = [
    "ATTESTATION_SCHEMA",
    "ATTEST_DIR",
    "LEDGER_FIELDS",
    "LEDGER_PATH",
    "TicketPlan",
    "TicketResult",
    "WaveAttestation",
    "WavePlan",
    "WaveResults",
    "append_wave_ledger_entry",
    "attestation_path",
    "load_attestation",
    "run_wave",
    "verify_attestation",
    "verify_wave_ledger",
]

#: Schema tag stamped into every attestation (lets a future reader version-gate).
ATTESTATION_SCHEMA = "daslab.attestation.v1"

#: Default committed attestation directory (TRACKED — never gitignored; ADR-0031 §4).
ATTEST_DIR: Path = ROOT / "metrics" / "attestations"

#: Default committed wave-ledger path (TRACKED — never gitignored; ADR-0032 §1).
#: This is the append-only hash-chained ledger — NOT the gitignored ``board/.wave-log``
#: (human KPI scratch) and NOT the gitignored ``board/.events.jsonl`` runtime store.
LEDGER_PATH: Path = ROOT / "board" / "wave-ledger.jsonl"

#: The exact, ordered field set of one committed wave-ledger entry (ADR-0032 §1) —
#: the single SSOT the reconciliation validator (DAS-1506) reuses; no more, no less.
LEDGER_FIELDS: tuple[str, ...] = (
    "run_id",
    "wave",
    "ticket_ids",
    "attestation_path",
    "attestation_hash",
    "prev_hash",
    "self_hash",
    "created_at",
)

#: Genesis sentinel for the first attestation in a store (no prior receipt) — and,
#: reused verbatim, for the first line of the wave-ledger chain (ADR-0032 §1).
_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64


# ---------------------------------------------------------------------------
# Typed inputs — the routing DECISION (plan) and collected OUTCOMES (results)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TicketPlan:
    """One ticket's routing decision within a wave (already taken by the LLM).

    Attributes:
        ticket_id:   DAS-NNNN dispatched unit.
        role:        Role key the ticket was routed to (``.claude/agents/<key>``).
        model:       Explicit model dispatched (LAW 3 — never inferred here).
        from_status: Lifecycle status the ticket moved FROM (wave-open state).
        to_status:   Lifecycle status the dispatch moved it TO (routing target).
    """

    ticket_id: str
    role: str
    model: str
    from_status: str = "todo"
    to_status: str = "in_progress"


@dataclass(frozen=True)
class WavePlan:
    """The routing DECISION for one wave — the immutable ``run_wave`` input.

    Mirrors exactly what ADR-0023's ``manifest.json`` records: the caller-minted
    ULID ``run_id``, the 1-based ``wave`` index, the ordered ticket set with its
    per-ticket ``{role, model}`` routing, plus the anchor ticket, pending
    interrupts and goal/engine_version.  It is the decision, already taken —
    ``run_wave`` cannot alter it.
    """

    run_id: str
    wave: int
    goal: str
    engine_version: str
    tickets: list[TicketPlan]
    anchor_ticket: str | None = None
    pending_interrupts: list[str] = field(default_factory=list)

    def anchor(self) -> str:
        """The run's anchor ticket (envelope law) — explicit, else the first ticket."""
        if self.anchor_ticket:
            return self.anchor_ticket
        if not self.tickets:
            raise ValueError("WavePlan has no tickets and no anchor_ticket")
        return self.tickets[0].ticket_id


@dataclass(frozen=True)
class TicketResult:
    """One ticket's collected OUTCOME — the reality the orchestrator observed.

    Carries exactly what ``dispatch_emitter.DispatchRecord`` + ``snapshot_evidence``
    need.  ``run_id`` is the per-dispatch join key that pairs this ticket's
    ``run_start`` / ``run_end`` / ``span`` triplet and keys its committed evidence
    file (defaults to a deterministic ``<plan.run_id>-<ticket_id>`` when absent).

    Attributes:
        ticket_id:    DAS-NNNN (must match a ``TicketPlan.ticket_id``).
        outcome:      Run outcome — ``metrics_lib`` success vocabulary.
        merged_pr:    Merged-PR evidence (R-9; truthy ⇒ counts).
        ci_status:    CI status (R-9 ``GREEN_CI``).
        t7_pass:      T7 pass flag (robust truthiness).
        t7_score:     T7 impact score.
        start / end:  Run/span window, caller-supplied ISO-8601 ``Z`` strings.
        final_status: The lifecycle status the ticket reached (wave-close state /
                      completion record status).
        run_id:       Per-dispatch join key; derived deterministically if empty.
        input_tokens/output_tokens/cached_input_tokens: span token usage.
        span_status:  Span outcome ∈ {``ok``, ``error``}.
        output:       The agent's produced output text (OUTPUT guardrail screen).
    """

    ticket_id: str
    outcome: str
    merged_pr: Any
    ci_status: str
    t7_pass: Any
    t7_score: float
    start: str
    end: str
    final_status: str = "done"
    run_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    span_status: str = "ok"
    output: str = ""


@dataclass(frozen=True)
class WaveResults:
    """The collected OUTCOMES for one wave — the immutable ``run_wave`` input.

    Attributes:
        tickets:              Per-ticket results (one per dispatched ticket).
        request_satisfied:    Progress-ledger flag — the wave's request is met.
        in_loop:              Progress-ledger flag — the run is still looping.
        progress_being_made:  Progress-ledger flag — forward progress observed.
        next_tickets:         Progress-ledger — ids the next wave should pick up.
        instruction:          Progress-ledger — steer for the next wave (may be "").
    """

    tickets: list[TicketResult]
    request_satisfied: bool = True
    in_loop: bool = False
    progress_being_made: bool = True
    next_tickets: list[str] = field(default_factory=list)
    instruction: str = ""

    def by_id(self) -> dict[str, TicketResult]:
        return {r.ticket_id: r for r in self.tickets}


@dataclass(frozen=True)
class WaveAttestation:
    """The committed receipt ``run_wave`` returns and writes (ADR-0031 §4)."""

    run_id: str
    wave: int
    payload: dict[str, Any]
    path: Path

    @property
    def self_hash(self) -> str:
        return str(self.payload["attest_chain"]["self"])

    @property
    def prev_hash(self) -> str:
        return str(self.payload["attest_chain"]["prev"])


# ---------------------------------------------------------------------------
# Canonical hashing (ADR-0023 §2 self-exclusion convention — mirrors
# pulse_checkpoint.compute_ledger_hash; never a re-implementation of the store).
# ---------------------------------------------------------------------------


def _canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON encoding (sorted keys, compact separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256_bytes(data: bytes) -> str:
    """SHA-256 of raw bytes as a ``sha256:<hex>`` digest — the byte-level primitive.

    Reused for the ledger's ``attestation_hash`` (SHA-256 of the committed
    attestation FILE's exact bytes), so a swapped/reformatted receipt changes it.
    """
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _sha256(obj: Any) -> str:
    """SHA-256 over an object's canonical JSON bytes (sorted keys, compact)."""
    return _sha256_bytes(_canonical_bytes(obj))


def _attest_self_hash(payload: dict[str, Any]) -> str:
    """SHA-256 of the attestation with ``attest_chain.self`` excluded (the preimage)."""
    preimage = dict(payload)
    chain = dict(preimage.get("attest_chain", {}))
    chain.pop("self", None)
    preimage["attest_chain"] = chain
    return _sha256(preimage)


# ---------------------------------------------------------------------------
# Attestation store helpers (also used by the CI validator, DAS-1500)
# ---------------------------------------------------------------------------


def attestation_path(run_id: str, attest_dir: Path | str | None = None) -> Path:
    """Committed attestation path for a run: ``<attest_dir>/<run_id>.json``."""
    return Path(attest_dir if attest_dir is not None else ATTEST_DIR) / f"{run_id}.json"


def load_attestation(path: Path | str) -> dict[str, Any]:
    """Load an attestation payload from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_attestation(payload: dict[str, Any]) -> list[str]:
    """Return integrity problems for one attestation; empty == the receipt verifies.

    Recomputes the self-hash over the canonical preimage (``attest_chain.self``
    excluded) and confirms it matches the stored value — a tampered receipt
    breaks the chain and is detectable.  Does NOT raise.
    """
    errors: list[str] = []
    if payload.get("schema") != ATTESTATION_SCHEMA:
        errors.append(f"unexpected schema {payload.get('schema')!r}")
    chain = payload.get("attest_chain")
    if not isinstance(chain, dict) or "prev" not in chain or "self" not in chain:
        errors.append("attest_chain must carry 'prev' and 'self'")
        return errors
    recomputed = _attest_self_hash(payload)
    if recomputed != chain.get("self"):
        errors.append(
            f"attest_chain.self mismatch: stored {chain.get('self')!r} != recomputed {recomputed!r}"
        )
    return errors


def _chain_tip(attest_dir: Path, exclude_run_id: str) -> str:
    """Return the ``self`` hash of the latest existing attestation, else genesis.

    Deterministic ordering: the tip is the existing attestation with the greatest
    ``(created_at, run_id)`` — so a new receipt links to the most recent prior
    one.  The current run's own file (if it is being overwritten) is excluded so a
    re-run never chains to a stale copy of itself.
    """
    if not attest_dir.exists():
        return _GENESIS_PREV_HASH
    best_key: tuple[str, str] | None = None
    best_self: str | None = None
    for p in sorted(attest_dir.glob("*.json")):
        if p.stem == exclude_run_id:
            continue
        try:
            payload = load_attestation(p)
        except (OSError, json.JSONDecodeError):
            continue
        chain = payload.get("attest_chain")
        if not isinstance(chain, dict) or "self" not in chain:
            continue
        key = (str(payload.get("created_at", "")), str(payload.get("run_id", "")))
        if best_key is None or key > best_key:
            best_key, best_self = key, str(chain["self"])
    return best_self if best_self is not None else _GENESIS_PREV_HASH


# ---------------------------------------------------------------------------
# Wave-ledger helpers (ADR-0032 §1 — the SECOND committed hash chain).
# The ledger's own prev/self chain is INDEPENDENT of each attestation's
# ``attest_chain``: it links every appended line across the WHOLE file, in append
# order, self-excluded.  REUSES the canonical hashing (``_sha256``), the byte
# hasher (``_sha256_bytes``), and the genesis sentinel (``_GENESIS_PREV_HASH``)
# above — never a re-implementation.
# ---------------------------------------------------------------------------


def _ledger_self_hash(entry: dict[str, Any]) -> str:
    """SHA-256 of a ledger entry with ``self_hash`` excluded (its preimage).

    Mirrors the ADR-0023 §2 self-exclusion convention used for ``attest_chain``
    (see :func:`_attest_self_hash`) — an entry cannot hash over its own digest.
    """
    preimage = {k: v for k, v in entry.items() if k != "self_hash"}
    return _sha256(preimage)


def _ledger_chain_tip(ledger_path: Path) -> str:
    """Return the ``self_hash`` of the last appended ledger line, else genesis.

    The ledger is strictly append-ordered, so the chain tip is simply the last
    well-formed line's ``self_hash`` — a new entry's ``prev_hash`` links to it (or
    to the genesis sentinel ``sha256:0×64`` when the file is empty/absent).
    """
    if not ledger_path.exists():
        return _GENESIS_PREV_HASH
    tip = _GENESIS_PREV_HASH
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        sh = entry.get("self_hash")
        if isinstance(sh, str) and sh:
            tip = sh
    return tip


def _attestation_repo_path(out_path: Path, ledger_path: Path) -> str:
    """Repo-relative POSIX path of the co-produced attestation, for the ledger entry.

    Prefers the module ``ROOT`` (so a committed sample / real wave records
    ``metrics/attestations/<run_id>.json``); falls back to the ledger's own repo
    root (``<ledger>/../..``) for a hermetic ``tmp_path`` tree, then to the absolute
    path.  Deterministic for any real committed wave.
    """
    for base in (ROOT, ledger_path.resolve().parent.parent):
        try:
            return out_path.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return out_path.resolve().as_posix()


def append_wave_ledger_entry(
    *,
    ledger_path: Path,
    run_id: str,
    wave: int,
    ticket_ids: list[str],
    attestation_out_path: Path,
    attestation_bytes: bytes,
    created_at: str,
) -> dict[str, Any]:
    """Atomically append ONE hash-chained entry to ``board/wave-ledger.jsonl``.

    LOAD-BEARING (ADR-0032 §1): raises on any I/O failure — the caller never
    swallows it, so a wave's ledger line is produced iff its attestation is.  The
    entry carries exactly :data:`LEDGER_FIELDS`; ``ticket_ids`` is sorted (matching
    the attestation's ``tickets``), ``attestation_hash`` is the SHA-256 of the
    committed attestation FILE's exact bytes, ``self_hash`` excludes itself, and
    ``prev_hash`` links the previous ledger line (genesis for the first).  The line
    is serialised once and written in a single append, so a line is never partial.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "run_id": run_id,
        "wave": wave,
        "ticket_ids": sorted(ticket_ids),
        "attestation_path": _attestation_repo_path(attestation_out_path, ledger_path),
        "attestation_hash": _sha256_bytes(attestation_bytes),
        "prev_hash": _ledger_chain_tip(ledger_path),
        "self_hash": "",  # filled below (self-excluded preimage)
        "created_at": created_at,
    }
    entry["self_hash"] = _ledger_self_hash(entry)
    line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return entry


def verify_wave_ledger(
    ledger_path: Path | str,
    *,
    attest_dir: Path | str | None = None,
    reconcile_attestations: bool = True,
) -> list[str]:
    """Reconcile ``board/wave-ledger.jsonl`` against its committed attestations.

    The SSOT reconciliation primitive (ADR-0032 §1).  It is the single place the
    ledger's integrity is decided, so the recovery drill (``kill_drill``) and the
    ``check_wave_reconciliation`` collect-time gate (DAS-1506) both reconcile
    THROUGH it — never a forked re-implementation.  Reuses the ledger's own
    hashing (:func:`_ledger_self_hash`), the genesis sentinel
    (:data:`_GENESIS_PREV_HASH`), the field set (:data:`LEDGER_FIELDS`), the byte
    hasher (:func:`_sha256_bytes`), and the attestation reader/verifier
    (:func:`attestation_path` / :func:`load_attestation` / :func:`verify_attestation`).

    Returns a list of problem strings; **empty ⇒ the ledger is a valid unbroken
    hash chain with NO gap and NO duplicate that reconciles against every
    attestation**.  Does NOT raise (a caller decides fail-closed vs. report).

    Checks, in order:

      1. **Well-formed** — each non-empty line is JSON carrying exactly
         :data:`LEDGER_FIELDS` (no more, no less).
      2. **No duplicate** — no two entries share a ``(run_id, wave)`` pair.
      3. **Chain continuity** — in append order the entries form an unbroken chain:
         the first ``prev_hash`` is genesis, each subsequent ``prev_hash`` equals
         the prior line's ``self_hash`` (a dropped line ⇒ GAP ⇒ break), and every
         ``self_hash`` recomputes over its self-excluded preimage (a tampered line
         ⇒ break).
      4. **Bijection** (when ``reconcile_attestations`` and ``attest_dir`` given) —
         each entry's ``metrics/attestations/<run_id>.json`` exists, verifies
         (:func:`verify_attestation`), and its ``attestation_hash`` equals the
         SHA-256 of that committed file's exact bytes, with the attestation's
         ``tickets`` / ``wave`` matching the entry; and NO attestation in
         ``attest_dir`` is an orphan (every committed receipt has a ledger entry).

    An empty/absent ledger is inert-by-design: it reconciles (returns ``[]``).
    """
    ledger_path = Path(ledger_path)
    problems: list[str] = []
    if not ledger_path.exists():
        return problems

    entries: list[dict[str, Any]] = []
    for lineno, raw in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {lineno}: malformed JSON ({exc})")
            continue
        if set(entry) != set(LEDGER_FIELDS):
            problems.append(
                f"line {lineno}: fields {sorted(entry)} != required {sorted(LEDGER_FIELDS)}"
            )
            continue
        entries.append(entry)

    # (2) no duplicate (run_id, wave) — a repeated wave entry.
    seen: set[tuple[str, Any]] = set()
    for entry in entries:
        key = (str(entry.get("run_id")), entry.get("wave"))
        if key in seen:
            problems.append(f"duplicate ledger entry for run_id={key[0]!r} wave={key[1]!r}")
        seen.add(key)

    # (3) chain continuity in append order (dropped line ⇒ gap; tampered ⇒ break).
    expected_prev = _GENESIS_PREV_HASH
    for entry in entries:
        run_id = str(entry.get("run_id"))
        wave = entry.get("wave")
        if entry.get("prev_hash") != expected_prev:
            problems.append(
                f"broken chain at run_id={run_id!r} wave={wave!r}: "
                f"prev_hash {entry.get('prev_hash')!r} != expected {expected_prev!r} "
                "(a dropped or reordered wave-ledger line)"
            )
        recomputed = _ledger_self_hash(entry)
        if recomputed != entry.get("self_hash"):
            problems.append(
                f"tampered entry at run_id={run_id!r} wave={wave!r}: "
                f"self_hash {entry.get('self_hash')!r} != recomputed {recomputed!r}"
            )
        expected_prev = str(entry.get("self_hash"))

    # (4) bijection ledger <-> committed attestations.
    if reconcile_attestations and attest_dir is not None:
        attest_dir = Path(attest_dir)
        ledger_run_ids: set[str] = set()
        for entry in entries:
            run_id = str(entry.get("run_id"))
            ledger_run_ids.add(run_id)
            att_path = attestation_path(run_id, attest_dir)
            if not att_path.exists():
                problems.append(f"ledger entry run_id={run_id!r} has no committed attestation")
                continue
            try:
                payload = load_attestation(att_path)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"attestation for run_id={run_id!r} unreadable ({exc})")
                continue
            att_problems = verify_attestation(payload)
            if att_problems:
                problems.append(f"attestation for run_id={run_id!r} fails verify: {att_problems}")
            got_hash = _sha256_bytes(att_path.read_bytes())
            if got_hash != entry.get("attestation_hash"):
                problems.append(
                    f"attestation_hash mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('attestation_hash')!r} != file {got_hash!r} "
                    "(a swapped or reformatted receipt)"
                )
            if payload.get("tickets") != entry.get("ticket_ids"):
                problems.append(
                    f"ticket set mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('ticket_ids')!r} != attestation {payload.get('tickets')!r}"
                )
            if payload.get("wave") != entry.get("wave"):
                problems.append(
                    f"wave mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('wave')!r} != attestation {payload.get('wave')!r}"
                )
        if attest_dir.exists():
            for att_file in sorted(attest_dir.glob("*.json")):
                if att_file.stem not in ledger_run_ids:
                    problems.append(
                        f"orphan attestation {att_file.name}: committed receipt with no ledger entry"
                    )

    return problems


# ---------------------------------------------------------------------------
# Mechanic helpers (each REUSES a shipped primitive verbatim)
# ---------------------------------------------------------------------------


def _dispatch_run_id(plan: WavePlan, result: TicketResult) -> str:
    """The per-dispatch join key — caller-supplied, else deterministic."""
    return result.run_id or f"{plan.run_id}-{result.ticket_id}"


def _build_records(plan: WavePlan, results: WaveResults) -> list[_de.DispatchRecord]:
    """Pair each plan ticket with its result into a ``DispatchRecord`` (pure)."""
    by_id = results.by_id()
    records: list[_de.DispatchRecord] = []
    for tp in plan.tickets:
        r = by_id.get(tp.ticket_id)
        if r is None:
            raise ValueError(f"no result collected for planned ticket {tp.ticket_id!r}")
        records.append(
            _de.DispatchRecord(
                ticket_id=tp.ticket_id,
                run_id=_dispatch_run_id(plan, r),
                goal=plan.goal,
                engine_version=plan.engine_version,
                model=tp.model,
                role_key=tp.role,
                start=r.start,
                end=r.end,
                outcome=r.outcome,
                merged_pr=r.merged_pr,
                ci_status=r.ci_status,
                t7_pass=r.t7_pass,
                t7_score=r.t7_score,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cached_input_tokens=r.cached_input_tokens,
                span_status=r.span_status,
            )
        )
    return records


def _stamp_run_id_frontmatter(ticket_path: Path, run_id: str) -> bool:
    """Idempotently set ``run_id: <run_id>`` in a ticket's YAML frontmatter.

    The stamp is the committed audit-trail marker that links a ticket closed
    through an attested wave to that wave's ``run_id`` — the exact field the
    reconciliation coverage arm keys on (``check_wave_reconciliation`` §COVERAGE).
    It is a pure text rewrite that preserves every other line: an existing
    ``run_id`` line is REPLACED (never duplicated) and an absent one is inserted
    just before the closing ``---``, so a re-run on an already-stamped file is a
    byte no-op.  Returns ``True`` iff the file was rewritten.  Never raises for a
    malformed / frontmatter-less file (returns ``False`` — the caller isolates I/O).
    """
    text = ticket_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    header, rest = text[3:end], text[end:]
    out_lines: list[str] = []
    replaced = False
    for line in header.split("\n"):
        key = line.partition(":")[0].strip()
        if key == "run_id" and not line.lstrip().startswith("#"):
            out_lines.append(f"run_id: {run_id}")
            replaced = True
        else:
            out_lines.append(line)
    if not replaced:
        out_lines.append(f"run_id: {run_id}")
    new_text = "---" + "\n".join(out_lines) + rest
    if new_text == text:
        return False
    ticket_path.write_text(new_text, encoding="utf-8")
    return True


def _stamp_wave_run_ids(plan: WavePlan, board_dir: Path) -> None:
    """Stamp ``run_id: <plan.run_id>`` into each planned ticket's frontmatter.

    Post-decision + failure-isolated PER TICKET (ADR-0031 §2): a ticket whose
    file is absent from ``board_dir`` is logged and skipped, and any per-ticket
    I/O error is caught — a missing/unreadable ticket NEVER crashes the wave, so
    the load-bearing attestation + ledger still commit.  This gives the coverage
    arm real subjects (a done ticket carrying a ``run_id`` MUST have a covering
    ledger entry) and turns a FORGED ``run_id`` into a reconciliation failure.
    The whole step runs only inside the ``organism_emit``-gated body, so a
    flag-off wave stamps nothing (flag-on == flag-off dispatch decisions).
    """
    for tp in plan.tickets:
        try:
            matches = sorted(Path(board_dir).glob(f"{tp.ticket_id}-*.md"))
            if not matches:
                sys.stderr.write(
                    f"wave_runner: no ticket file for {tp.ticket_id} in {board_dir} "
                    "— run_id not stamped (audit-trail gap logged, wave continues)\n"
                )
                continue
            _stamp_run_id_frontmatter(matches[0], plan.run_id)
        except Exception as exc:  # noqa: BLE001 — per-ticket stamp is failure-isolated
            sys.stderr.write(
                f"wave_runner: failed to stamp run_id on {tp.ticket_id}: "
                f"{type(exc).__name__}: {exc}\n"
            )


def _run_guardrails(
    plan: WavePlan,
    results: WaveResults,
    *,
    board_dir: Path,
    routing_path: Path,
    guardrails_dir: Path,
    created_at: str,
) -> dict[str, str]:
    """Run each ticket's INPUT/OUTPUT guardrail on its collected output.

    Failure-isolated (ADR-0031 §2 — the OPTIONAL tripwire never aborts the
    receipt): a per-ticket guardrail exception is caught and recorded as
    ``"error"``.  ``run_agent`` is a no-op that replays the already-collected
    output (no LLM, no re-dispatch of live work).  Returns ``{ticket_id: verdict}``.
    """
    by_id = results.by_id()
    now = (lambda: created_at[:10]) if len(created_at) >= 10 else (lambda: created_at)
    verdicts: dict[str, str] = {}
    for tp in plan.tickets:
        matches = sorted(Path(board_dir).glob(f"{tp.ticket_id}-*.md"))
        if not matches:
            verdicts[tp.ticket_id] = "no_ticket_file"
            continue
        output = by_id[tp.ticket_id].output

        def _replay(_ctx: Any, _attempt: int, _out: str = output) -> str:
            return _out

        try:
            res = _gd.guardrail_dispatch(
                matches[0],
                _replay,
                routing_path=routing_path,
                board_dir=Path(board_dir),
                guardrails_dir=guardrails_dir,
                now=now,
            )
            verdicts[tp.ticket_id] = res.outcome
        except Exception as exc:  # noqa: BLE001 — OPTIONAL step is failure-isolated
            verdicts[tp.ticket_id] = f"error:{type(exc).__name__}"
    return verdicts


# ---------------------------------------------------------------------------
# The single deterministic entry point
# ---------------------------------------------------------------------------


def run_wave(
    plan: WavePlan,
    results: WaveResults,
    *,
    created_at: str,
    store_path: Path | str | None = None,
    runs_dir: Path | None = None,
    attest_dir: Path | str | None = None,
    ledger_path: Path | str | None = None,
    evidence_dir: Path | str | None = None,
    tickets_dir: Path | None = None,
    board_dir: Path | None = None,
    routing_path: Path | None = None,
    guardrails_dir: Path | None = None,
    organism_emit: bool = True,
    run_guardrails: bool = True,
) -> WaveAttestation | None:
    """Deterministically execute the POST-DECISION mechanics of one wave.

    Given ``(plan, results)`` the runner performs, in ADR-0031 §3 order and via
    the existing libraries only: (1) a wave-open checkpoint, (2) the
    ``run_start`` / ``run_end`` / ``span`` triplet per dispatch, (3) per-role
    guardrail tripwires on the outputs, (4) the progress-ledger + task-ledger +
    per-ticket completions + wave-close checkpoint, (5) committed redacted
    evidence per dispatch, (6) a committed, doubly hash-chained
    :class:`WaveAttestation`, and (7) an ATOMIC, committed, hash-chained entry
    appended to the TRACKED ``board/wave-ledger.jsonl`` (ADR-0032 §1).  It reads
    no clock and makes no routing decision.

    The emission (2), attestation (6), and ledger co-write (7) are LOAD-BEARING —
    they raise on failure so a wave's done-ness genuinely flows through this call,
    and the attestation + its ledger line are ONE atomic unit (both produced, or
    ``run_wave`` raises — never one without the other).  Only the OPTIONAL
    guardrail tripwire (3) is failure-isolated internally.

    Args:
        plan:            The routing DECISION (immutable).
        results:         The collected OUTCOMES (immutable).
        created_at:      Wave-level ISO-8601 ``Z`` timestamp (caller-supplied —
                         no clock is read; per-dispatch spans use ``results`` ts).
        store_path:      Event store path (default: live ``board/.events.jsonl``).
        runs_dir:        Run-artifact tree (default: canonical ``board/runs/``).
        attest_dir:      Committed attestation dir (default: ``metrics/attestations``).
        ledger_path:     Committed wave-ledger file the entry is appended to
                         (default: TRACKED ``board/wave-ledger.jsonl``; ADR-0032 §1).
        evidence_dir:    Committed evidence dir (default: ``metrics/evidence``).
        tickets_dir:     Ticket dir for the checkpoint board-hash (default: canonical).
        board_dir:       Ticket dir the guardrails screen against (default:
                         ``tickets_dir`` or canonical ``board/tickets``).
        routing_path:    ROUTING.md for guardrail role resolution (default: canonical).
        guardrails_dir:  Per-role guardrail package (default: canonical).
        organism_emit:   The ADR-0025 gate.  ``False`` ⇒ no-op (writes nothing,
                         returns ``None``) so flag-on == flag-off dispatch holds.
        run_guardrails:  Toggle the OPTIONAL guardrail tripwire (default on).

    Returns:
        The committed :class:`WaveAttestation`, or ``None`` when ``organism_emit``
        is off (the runner did nothing).
    """
    if not organism_emit:
        return None  # flag-off: byte-identical dispatch, zero post-decision writes.

    attest_dir = Path(attest_dir) if attest_dir is not None else ATTEST_DIR
    evidence_dir = Path(evidence_dir) if evidence_dir is not None else _se.EVIDENCE_DIR
    board_dir = board_dir if board_dir is not None else (tickets_dir or _pc.DEFAULT_TICKETS_DIR)
    routing_path = routing_path if routing_path is not None else _gd.DEFAULT_ROUTING
    guardrails_dir = guardrails_dir if guardrails_dir is not None else _gr.DEFAULT_GUARDRAILS_DIR

    # Validate inputs up front (fail loud, before ANY side effect): every planned
    # ticket must have a collected result.  ``_build_records`` is the pure pairing
    # that raises for a missing result, so build it here and reuse it at step 2.
    records = _build_records(plan, results)

    anchor = plan.anchor()
    by_id = results.by_id()
    open_states = {tp.ticket_id: tp.from_status for tp in plan.tickets}
    close_states = {tp.ticket_id: by_id[tp.ticket_id].final_status for tp in plan.tickets}

    # (1) Wave-OPEN checkpoint — the step-4 mechanic at the wave-open boundary.
    _pc.write_wave_checkpoint(
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_id=anchor,
        curr_ticket_states=open_states,
        pending_interrupts=plan.pending_interrupts,
        created_at=created_at,
        store_path=store_path,
        tickets_dir=tickets_dir,
        runs_dir=runs_dir,
        emit_event=False,
    )

    # (1b) Stamp the wave's run_id into each planned ticket's frontmatter — the
    # committed audit-trail marker the coverage arm keys on.  Post-decision and
    # failure-isolated per ticket (a missing ticket file is logged, never crashes
    # the wave); it runs only in this organism_emit-gated body, so a flag-off wave
    # stamps nothing and dispatch decisions stay byte-identical.
    _stamp_wave_run_ids(plan, board_dir)

    # (2) Run-lifecycle events — run_start / run_end / span per dispatch (LOAD-BEARING).
    events = _de.emit_wave(records, store_path=store_path)
    emitted_counts = {
        "run_start": sum(1 for e in events if e.get("event_type") == "run_start"),
        "run_end": sum(1 for e in events if e.get("event_type") == "run_end"),
        "span": sum(1 for e in events if e.get("event_type") == "span"),
    }

    # (3) Per-role guardrail tripwires on the collected outputs (OPTIONAL / isolated).
    guardrail_verdicts: dict[str, str] = {}
    if run_guardrails:
        guardrail_verdicts = _run_guardrails(
            plan,
            results,
            board_dir=board_dir,
            routing_path=routing_path,
            guardrails_dir=guardrails_dir,
            created_at=created_at,
        )

    # (4) Ledgers + per-ticket completions + wave-CLOSE checkpoint.
    for tp in plan.tickets:
        _pc.append_ticket_completion(
            run_id=plan.run_id,
            ticket_id=tp.ticket_id,
            status=by_id[tp.ticket_id].final_status,
            wave=plan.wave,
            created_at=created_at,
            runs_dir=runs_dir,
        )
    _tl.build_task_ledger(
        run_id=plan.run_id,
        facts={"given": [f"wave {plan.wave} of goal {plan.goal}"],
               "known": sorted(close_states)},
        plan=[f"{tp.ticket_id} -> {tp.role} ({tp.model})" for tp in plan.tickets],
        created_at=created_at,
        goal=plan.goal,
        wave=plan.wave,
        runs_dir=runs_dir,
    )
    progress_ledger_path = _cl.write_progress_ledger(
        run_id=plan.run_id,
        request_satisfied=results.request_satisfied,
        in_loop=results.in_loop,
        progress_being_made=results.progress_being_made,
        next_tickets=results.next_tickets,
        instruction=results.instruction,
        runs_dir=runs_dir,
    )
    close_cp = _pc.write_wave_checkpoint(
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_id=anchor,
        curr_ticket_states=close_states,
        pending_interrupts=plan.pending_interrupts,
        created_at=created_at,
        store_path=store_path,
        tickets_dir=tickets_dir,
        runs_dir=runs_dir,
        emit_event=False,
    )

    # (5) Committed, redacted evidence per dispatch run_id (REUSE snapshot_evidence).
    evidence_run_ids = sorted({_dispatch_run_id(plan, by_id[tp.ticket_id]) for tp in plan.tickets})
    for rid in evidence_run_ids:
        _se.write_run_evidence(events, rid, evidence_dir)

    # (6) The committed, doubly hash-chained WaveAttestation.
    counted = sum(1 for e in events if _se._is_counted_completion(e))
    ledger_digest = _sha256(json.loads(progress_ledger_path.read_text(encoding="utf-8")))
    evidence_digest = _sha256(
        {rid: json.loads(_se.evidence_path(evidence_dir, rid).read_text(encoding="utf-8"))
         for rid in evidence_run_ids}
    )
    payload: dict[str, Any] = {
        "schema": ATTESTATION_SCHEMA,
        "run_id": plan.run_id,
        "wave": plan.wave,
        "engine_version": plan.engine_version,
        "created_at": created_at,
        "tickets": sorted(tp.ticket_id for tp in plan.tickets),
        "mechanics": {
            "checkpoint_open": True,
            "guardrails_run": bool(run_guardrails),
            "events_emitted": emitted_counts,
            "ledger_written": True,
            "evidence_written": True,
            "checkpoint_close": True,
        },
        "guardrail_verdicts": guardrail_verdicts,
        "counts": {"dispatched": len(plan.tickets), "counted_completions": counted},
        "event_digest": _sha256(events),
        "evidence": {
            "dir": "metrics/evidence",
            "run_ids": evidence_run_ids,
            "digest": evidence_digest,
        },
        "ledger_digest": ledger_digest,
        "ledger_hashes": dict(close_cp["ledger_hashes"]),
        "attest_chain": {
            "prev": _chain_tip(attest_dir, exclude_run_id=plan.run_id),
            "self": "",  # filled below (self-excluded preimage)
        },
    }
    payload["attest_chain"]["self"] = _attest_self_hash(payload)

    out_path = attestation_path(plan.run_id, attest_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # (7) The committed, hash-chained wave-ledger entry — ATOMIC with the attestation
    # just written and equally LOAD-BEARING (ADR-0032 §1): it RAISES on failure, so a
    # wave that commits done-ness cannot leave the attestation without its reconciling
    # ledger line.  ``attestation_hash`` binds the exact committed attestation bytes.
    wave_ledger_path = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    append_wave_ledger_entry(
        ledger_path=wave_ledger_path,
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_ids=[tp.ticket_id for tp in plan.tickets],
        attestation_out_path=out_path,
        attestation_bytes=out_path.read_bytes(),
        created_at=created_at,
    )

    return WaveAttestation(run_id=plan.run_id, wave=plan.wave, payload=payload, path=out_path)
