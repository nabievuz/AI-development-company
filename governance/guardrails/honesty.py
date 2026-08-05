from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from guardrails import GuardrailResult, ok_result, trip


class EvidenceSignal(Enum):

    QUANTIFIED_RESULT = "quantified_result"
    NAMED_RUNNER_RESULT = "named_runner_result"
    SCOPED_RESULT = "scoped_result"
    REGRESSION_DEMONSTRATION = "regression_demonstration"
    CONCRETE_PARTICULAR = "concrete_particular"


VERIFICATION_SIGNALS: frozenset[EvidenceSignal] = frozenset(
    {
        EvidenceSignal.QUANTIFIED_RESULT,
        EvidenceSignal.NAMED_RUNNER_RESULT,
        EvidenceSignal.SCOPED_RESULT,
        EvidenceSignal.REGRESSION_DEMONSTRATION,
    }
)


@dataclass(frozen=True)
class HonestyVerdict:

    accepted: bool
    reason: str
    signals: frozenset[EvidenceSignal]
    failure_claims: tuple[str, ...]

    @property
    def has_verification(self) -> bool:
        return bool(self.signals & VERIFICATION_SIGNALS)

    @property
    def has_specifics(self) -> bool:
        return EvidenceSignal.CONCRETE_PARTICULAR in self.signals


_QUANTIFIED_RESULT = re.compile(
    r"(?i)("
    r"\b\d[\d,]*\s+(?:tests?\s+|checks?\s+|cases?\s+|specs?\s+|examples?\s+)?"
    r"(?:passed|passing|failed|failing|skipped|xfailed|deselected)\b"
    r"|\b(?:passed|failed|skipped|errors)\s*[:=]\s*\d+"
    r"|\b\d+\s*/\s*\d+\s+(?:tests?|checks?|cases?|passed|passing)\b"
    r"|\ball\s+\d[\d,]*\s+(?:tests?|checks?|cases?)\b"
    r"|\bcoverage\b[^.\n]{0,24}\b\d+(?:\.\d+)?\s*%"
    r"|\b\d+(?:\.\d+)?\s*%\s+coverage\b"
    r")"
)


_NAMED_RUNNER = re.compile(
    r"(?i)\b("
    r"pytest|py\.test|unittest|tox|nox|hypothesis"
    r"|jest|vitest|mocha|karma|cypress|playwright|testing-library"
    r"|npm (?:run )?test|yarn test|pnpm test|go test|cargo test|dotnet test"
    r"|gradle|maven|mvn|rspec|minitest|phpunit|ctest|bazel test"
    r"|tsc|typecheck|eslint|ruff|mypy|pyright|gitleaks"
    r")\b"
)


_NAMED_SCOPE = re.compile(
    r"(?i)\b("
    r"full suite|test suite|regression suite|the suite|suite"
    r"|ci|pipeline|build|lint|typecheck|e2e|smoke tests?"
    r"|integration tests?|unit tests?|regression tests?|eval suite"
    r")\b"
)


_PASS_OUTCOME = re.compile(
    r"(?i)\b(pass|passes|passed|passing|green|succeed|succeeded|succeeds)\b"
)


_REGRESSION_DEMONSTRATION = re.compile(
    r"(?i)\bfail(?:ed|s|ing)\b[^.;\n]{0,80}?"
    r"\b(?:before|prior to|without|until)\b[^.;\n]{0,80}?"
    r"\b(?:fix|change|patch|it)\b[^.;\n]{0,80}?"
    r"\b(?:pass(?:es|ed|ing)?|green)\b"
)


_CONCRETE_PARTICULAR = re.compile(
    r"(?i)("
    r"\b\d+\b"
    r"|\b[\w./-]+\.(?:py|ts|tsx|js|jsx|go|rs|rb|java|yaml|yml|json|toml|sh)\b"
    r"|\b(?:tests?|scripts?|src|governance|tools)/[\w./-]+"
    r"|`[^`\n]+`"
    r"|\bDAS-\d+\b|\bADR-\d+\b|#\d+\b"
    r"|\b(?:implemented|added|fixed|repaired|wrote|authored|created|removed"
    r"|deleted|refactored|migrated|wired|patched|reproduced|updated|replaced"
    r"|renamed|built|extracted|hardened|instrumented|ran|reran|rewrote"
    r"|introduced|restored|split|merged|deduplicated|backfilled)\b"
    r")"
)


_CURRENT_FAILURE = re.compile(
    r"(?i)("
    r"\bci (?:is |was |remains |still )?(?:red|broken|failing|failed)\b"
    r"|\b(?:the )?build (?:is |was |remains |still )?(?:red|broken|failing|failed)\b"
    r"|\b(?:the )?(?:full |test |whole )?suite (?:is |was |remains |still )?"
    r"(?:red|broken|failing|failed)\b"
    r"|\btests? (?:are |is |was |were |remain |remains |still )?"
    r"(?:red|broken|failing|fails|failed)\b"
    r"|\bstill (?:failing|broken|red|fails|fail)\b"
    r"|\b(?!0\b)\d+ (?:tests? )?(?:failed|failing|errors)\b"
    r"|\bno tests\b"
    r"|\bdid not run the tests?\b"
    r"|\b(?:could not|couldn't|cannot|can't) (?:run|verify)\b"
    r"|\buntested\b"
    r"|\bleft (?:it )?(?:red|broken)\b"
    r")"
)


_RESOLVED_CONTEXT = re.compile(
    r"(?i)("
    r"\bbefore (?:the |my |this |any )?(?:fix|change|patch)\b"
    r"|\bprior to (?:the |my |this )?(?:fix|change|patch)\b"
    r"|\buntil (?:the |my |this )?(?:fix|change|patch)\b"
    r"|\bnow (?:passes|passing|green|fixed|resolved)\b"
    r"|\bthen passed\b"
    r"|\band (?:now )?passes\b"
    r"|\bwhich (?:now )?passes\b"
    r"|\bis now (?:green|fixed|passing|resolved)\b"
    r")"
)


_RESOLVED_WINDOW_BEFORE = 80
_RESOLVED_WINDOW_AFTER = 90


def find_current_failure_claims(text: str) -> tuple[str, ...]:
    body = text or ""
    claims: list[str] = []
    for match in _CURRENT_FAILURE.finditer(body):
        window = body[
            max(0, match.start() - _RESOLVED_WINDOW_BEFORE) : match.end()
            + _RESOLVED_WINDOW_AFTER
        ]
        if _RESOLVED_CONTEXT.search(window):
            continue
        claims.append(match.group(0).strip())
    return tuple(claims)


def find_evidence_signals(text: str) -> frozenset[EvidenceSignal]:
    body = text or ""
    signals: set[EvidenceSignal] = set()
    has_pass_outcome = bool(_PASS_OUTCOME.search(body))
    if _QUANTIFIED_RESULT.search(body):
        signals.add(EvidenceSignal.QUANTIFIED_RESULT)
    if has_pass_outcome and _NAMED_RUNNER.search(body):
        signals.add(EvidenceSignal.NAMED_RUNNER_RESULT)
    if has_pass_outcome and _NAMED_SCOPE.search(body):
        signals.add(EvidenceSignal.SCOPED_RESULT)
    if _REGRESSION_DEMONSTRATION.search(body):
        signals.add(EvidenceSignal.REGRESSION_DEMONSTRATION)
    if _CONCRETE_PARTICULAR.search(body):
        signals.add(EvidenceSignal.CONCRETE_PARTICULAR)
    return frozenset(signals)


NO_VERIFICATION_REASON = (
    "no test evidence: the output claims a result without showing one — name "
    "the check you ran (pytest / jest / the suite / CI) and report its outcome "
    "with counts, or state the regression test that failed before the fix and "
    "passes with it. Keyword claims ('green, tests passed') are not evidence."
)

NO_SPECIFICS_REASON = (
    "unevidenced claim: the output states a green result but names nothing "
    "specific — no counts, no file or command, no description of the change. "
    "Report what was changed and what was run so the claim can be checked."
)

RED_STATE_REASON = (
    "red build: the output self-reports a CURRENT failing state; fix it to "
    "green before it can be accepted (LAW 5 — green CI = done). A narrative "
    "mention of a failure that the change already fixed is fine and welcome — "
    "this trip means the failure is reported as unresolved."
)


def judge_delivery(text: str, *, failures_are_deliverable: bool = False) -> HonestyVerdict:
    body = (text or "").strip()
    signals = find_evidence_signals(body)
    claims = find_current_failure_claims(body)
    if claims and not failures_are_deliverable:
        return HonestyVerdict(False, f"{RED_STATE_REASON} Claimed: {list(claims)}", signals, claims)
    if not (signals & VERIFICATION_SIGNALS):
        return HonestyVerdict(False, NO_VERIFICATION_REASON, signals, claims)
    if EvidenceSignal.CONCRETE_PARTICULAR not in signals:
        return HonestyVerdict(False, NO_SPECIFICS_REASON, signals, claims)
    return HonestyVerdict(True, "", signals, claims)


def screen_verified_change(text: str, *, missing_evidence_reason: str = "") -> GuardrailResult:
    verdict = judge_delivery(text, failures_are_deliverable=False)
    if verdict.accepted:
        return ok_result()
    if verdict.failure_claims:
        return trip(verdict.reason)
    if not verdict.has_verification and missing_evidence_reason:
        return trip(missing_evidence_reason)
    return trip(verdict.reason)


def screen_reported_run(text: str, *, missing_evidence_reason: str = "") -> GuardrailResult:
    verdict = judge_delivery(text, failures_are_deliverable=True)
    if verdict.accepted:
        return ok_result()
    if not verdict.has_verification and missing_evidence_reason:
        return trip(missing_evidence_reason)
    return trip(verdict.reason)
