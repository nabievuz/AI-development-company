
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "governance"))

from guardrails import GuardrailContext, runner

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"


def _roles() -> list[str]:
    return sorted(runner.load_role_table(_ROUTING).keys())


def _ctx(role: str, output: str) -> GuardrailContext:
    return GuardrailContext(
        role=role, role_dept="", ticket_id="DAS-1", ticket_dept="", output=output
    )


VECTORS: list[tuple[str, str, str]] = [

    ("backend-em",
     "Reviewed PR #42 against the acceptance criteria; CI is green. Approved and merged via GATE-3.",
     "Read through the diff for the payment module; the implementation looks reasonable overall and follows our conventions."),
    ("backend-eng-2",
     "Reproduced the failing test, fixed the broken pagination, and added a regression test; the full suite passed and CI is green.",
     "Wrote the new /orders endpoint and wired it into the router; shipped the handler."),
    ("cto",
     "ADR-0031 recorded: selected the dispatch event-emitter over polling; rationale and law-check captured. Decision: approved.",
     "Here are some thoughts on the architecture: the event-emitter and the polling approach each have tradeoffs we should weigh."),
    ("frontend-em",
     "Reviewed DAS-1502: CI is green and all acceptance criteria are met. Approved for merge (GATE-3); no changes requested.",
     "Looked over the frontend PR for the dashboard; the diff is readable and the component structure looks fine overall."),
    ("frontend-eng-1",
     "Implemented the responsive nav bar in React. Added Jest unit tests and Playwright e2e; CI is green, lint and build pass. All acceptance criteria checked.",
     "Rewrote the profile page markup and shipped the styling updates."),
    ("frontend-eng-2",
     "Built the settings modal component. Added Vitest tests and a Storybook snapshot; typecheck, lint and build are green in CI.",
     "Adjusted the footer spacing and swapped the hero image on the landing page."),
    ("qa-eng",
     "Authored 12 regression tests; ran the eval suite - 12 passed, accuracy 0.97, coverage 88%.",
     "Reviewed the ticket and everything looks good to me; shipping it."),
    ("qa-lead",
     "GATE-4 eval gate: accuracy 0.94 is at or above the 0.90 threshold - PASS. Release approved, no regressions blocking.",
     "The numbers came in around what we expected, so it seems okay overall."),
    ("sre-eng",
     "Wrote the deploy runbook and wired Grafana monitoring; rollback tested via canary revert, health-check green.",
     "Pushed the new build straight to production and it started up fine."),
    ("sre-lead",
     "GATE-5 deploy sign-off: canary healthy for 30m, observability dashboards green, rollback rehearsed - GO-LIVE approved.",
     "The pipeline is set up and the containers are running in the cluster."),
    ("security-eng",
     "Ran SAST plus gitleaks and a dependency scan and a red-team pass: 0 findings, no CVEs, nothing to remediate.",
     "Looked over the changes and nothing jumped out as risky."),
    ("backend-eng-1",
     "Implemented the change; added pytest tests and the full suite passed with CI green.",
     "Wrote the endpoint and shipped it."),
    ("security-lead",
     "Security review complete: signed-off. No plaintext secrets in the diff.",
     "Reviewed the changes; nothing obvious looks off to me."),

    ("board-member",
     "Board minutes DAS-1490: the Q3 hiring request is APPROVED by Board Member. Rationale: within the Q3 budget envelope. Law-check: complies with the Model Allocation Law.",
     "The board convened to review the Q3 hiring request. Members shared perspectives on the budget impact, and the discussion covered several concerns raised earlier."),
    ("ceo",
     "Strategy decision recorded: the Q3 goal is decomposed into epics E-1 through E-4 and APPROVED for the board queue. Rationale: focuses the fleet on ORGANISM. Law-check: honors the AI-Agent Lifecycle Law.",
     "The CEO reviewed the quarterly goals and outlined how the fleet might be organized across departments, weighing the tradeoffs before the next planning session."),
    ("chairman",
     "Board minutes: the Chairman rules that the ORGANISM directive is ratified with binding effect. Rationale: aligns all departments under one program. Law-check: consistent with the Founder-Approved Goal Queue Law.",
     "The Chairman opened the session and heard arguments from both departments about the proposed reorganization, then adjourned to consider the matter at the next sitting."),

    ("cpo",
     "Decision: approved the Q3 roadmap theme 'Reliability'. Rationale: aligns with GATE-1 KPI targets; law-check passed. Recorded in board minutes.",
     "I reviewed the options and gathered some notes on possible themes for next quarter, but nothing is final yet."),
    ("product-analyst",
     "Analysis: weekly active users rose 12% (from 4,200 to 4,704) over the last 30 days. Source: events pipeline. Recommendation: invest in the onboarding funnel; filed DAS-1500 as a follow-up ticket.",
     "Analysis: engagement appears to be trending upward this quarter based on qualitative feedback; recommend we keep investing in onboarding."),
    ("senior-pm",
     "PRD: Notification Preferences. Problem, goals, and user stories captured; acceptance criteria and success metrics defined. Spec filed in specs/notifications.md.",
     "Had a good chat with the team about notification ideas; we brainstormed a few directions and will circle back next week."),
    ("tech-writer",
     "Updated CHANGELOG.md with the new rollout entry and refreshed the API reference in docs/api.md to match the shipped behavior.",
     "Chatted with the backend team to understand the new endpoint behavior; still need to figure out where this belongs before writing anything."),

    ("cdo",
     "Design strategy decision recorded in ADR-0031: approved the token-first direction for the design system; rationale and law-check captured in board minutes.",
     "Reviewed the current design system and gathered notes from the team about the roadmap."),
    ("design-lead",
     "Design direction reviewed: the Figma mockups are token-compliant and the component spec was handed off to engineering to build.",
     "Met with the team and discussed priorities for next quarter; will follow up later."),
    ("product-designer",
     "Delivered the settings screen mockup in Figma with new button components mapped to design tokens.",
     "Wrote up some thoughts on the overall product roadmap and shared them with the team."),
    ("ux-researcher",
     "Synthesis of six usability sessions: the key finding is users miss the save action; recommendation is to move it into the primary toolbar.",
     "Scheduled interviews with five participants and set up the research repository."),

    ("cmo",
     "Decision: approved the Q3 brand relaunch campaign. Rationale: cheaper CAC on organic. Law-check: complies with the claims policy. Recorded in board-minutes.",
     "Some early thoughts on brand direction and a few channel ideas we might explore next quarter."),
    ("content-lead",
     "Drafted the launch blog post (620 words); on-brand and reviewed by the CMO. Saved to content/launch-post.md",
     "I feel the messaging should sound warm and human, and we can nail down the specifics a bit later."),
    ("growth-marketer",
     "Paid-social experiment results: CTR 2.3%, CAC down to $41, conversion +12% vs baseline. Recommend scaling the budget.",
     "We should try fresh creative angles and see how the audience responds over the next while."),
    ("seo-specialist",
     "Optimized the meta title and meta description for the pricing page; added JSON-LD structured data and 8 target keywords with search volume noted; canonical set.",
     "The landing page looks clean and the copy reads nicely on mobile."),

    ("coo",
     "Decision: approved the vendor renewal after a cost and law-check. Rationale: it comes in 18% cheaper; recorded in board-minutes.",
     "Gathered the vendor options and jotted some notes for the team to look over later."),
    ("finance-analyst",
     "Q3 infra burn is $4,200/mo, up 12% versus Q2. Recommendation: cap monthly token spend at $3,000.",
     "The budget looks healthy overall; no material concerns to flag this cycle and nothing that needs escalation."),
    ("legal-analyst",
     "Reviewed the data-retention change against GDPR Article 5; it is compliant. Recommendation: document the retention clause in the privacy policy.",
     "Looked over the new feature and it seems basically fine to ship; nothing jumped out at me as worrying."),
    ("support-lead",
     "Triaged the failed-login report, shared a workaround, and resolved it within SLA. Filed the recurring root cause to backend as DAS-1600.",
     "A customer wrote in about slow dashboards and general sluggishness; seems like something we may want to look into someday."),
]


def test_roster_complete() -> None:
    roles = _roles()
    assert len(roles) == 32, f"expected 32 ROUTING roles, got {len(roles)}"
    for role in roles:
        module = runner.load_guardrail_module(role)
        assert module is not None, f"no bespoke guardrail module for role {role!r}"
        assert getattr(module, "ROLE", None) == role, f"{role}: ROLE != filename stem"
        assert callable(getattr(module, "input_guardrail", None)), f"{role}: no input_guardrail"
        assert callable(getattr(module, "output_guardrail", None)), f"{role}: no output_guardrail"


def test_every_role_has_a_vector() -> None:


    assert {v[0] for v in VECTORS} == set(_roles())


def test_empty_output_always_trips() -> None:
    for role in _roles():
        module = runner.load_guardrail_module(role)
        ok, _ = module.output_guardrail(_ctx(role, ""))
        assert not ok, f"{role}: empty output must trip (base guardrail lost?)"


@pytest.mark.parametrize("role,passing,tripping", VECTORS, ids=[v[0] for v in VECTORS])
def test_output_guardrail_discipline(role: str, passing: str, tripping: str) -> None:
    module = runner.load_guardrail_module(role)
    ok_pass, fb_pass = module.output_guardrail(_ctx(role, passing))
    assert ok_pass, f"{role}: a legitimate deliverable was rejected: {fb_pass!r}"
    ok_trip, fb_trip = module.output_guardrail(_ctx(role, tripping))
    assert not ok_trip, f"{role}: an off-discipline output was NOT tripped"
    assert fb_trip.strip(), f"{role}: a tripped guardrail must carry feedback"


_REGRESSION_TRIPS = [
    ("ceo", "The CEO spent 20 minutes reviewing the options and will revisit them later."),
    ("board-member", "The board met for 45 minutes and heard the arguments before wrapping up."),
    ("chairman", "The Chairman spent 30 minutes hearing arguments and then adjourned the session."),
    ("backend-em", "I read the diff. The handler returned an error in the null branch; the old code blocked on the DB."),
    ("product-analyst", "Reviewed DAS-1500; engagement feels stronger this quarter, recommend more onboarding."),
    ("finance-analyst", "Reviewed DAS-1500 from 2026; the budget looks fine and nothing needs escalation."),
    ("support-lead", "The login issue is not yet resolved; still investigating with no workaround."),
]
_REGRESSION_PASSES = [
    ("backend-eng-2", "Reproduced the failing test and fixed the broken handler; the suite now passes and CI is green."),
    ("backend-em", "Reviewed the PR; the null-branch bug is fixed. Approved and merged."),
]


@pytest.mark.parametrize("role,output", _REGRESSION_TRIPS, ids=[r for r, _ in _REGRESSION_TRIPS])
def test_review_false_negatives_now_trip(role: str, output: str) -> None:
    module = runner.load_guardrail_module(role)
    ok, fb = module.output_guardrail(_ctx(role, output))
    assert not ok and fb.strip(), f"{role}: an off-discipline output should trip, got pass"


@pytest.mark.parametrize("role,output", _REGRESSION_PASSES, ids=[f"{r}-{i}" for i, (r, _) in enumerate(_REGRESSION_PASSES)])
def test_review_false_positives_now_pass(role: str, output: str) -> None:
    module = runner.load_guardrail_module(role)
    ok, fb = module.output_guardrail(_ctx(role, output))
    assert ok, f"{role}: a legitimate green deliverable was wrongly tripped: {fb!r}"
