#!/usr/bin/env python3
"""memory_lib.py — ArcRift memory governance.

Five controls over recall: **TTL** (per-type lifespan), **dedupe** (embedding
similarity), **trust-score** (provenance), **contradiction check**, and
**quarantine**. The LIVE store is ArcRift (an external MCP server using Ollama
nomic-embed-text embeddings); these pure functions implement the governance logic
over memory records so it can be enforced and tested in CI. Without a live
embedding model, dedupe uses a deterministic token-Jaccard proxy (documented) —
the live recall path uses real embedding similarity.

A memory record (the migrated schema, config/memory_governance.yaml):
    {id, content, project, mem_type, provenance, trust_score, created_at,
     ttl_days?, status?(active|quarantined|contradicted), contradicts?[ids]}
"""
from __future__ import annotations

import datetime as dt
import re


def parse_iso(ts: str) -> dt.datetime | None:
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' (or a date 'YYYY-MM-DD') into UTC-naive, or None."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(ts, fmt)
        except (ValueError, TypeError):
            continue
    return None


def trust_for(provenance: str, tiers: dict) -> float:
    """Map a provenance label to its trust score (unverified default)."""
    return float(tiers.get(str(provenance), tiers.get("unverified_claim", 0.0)))


def ttl_for(mem: dict, ttl_config: dict) -> float:
    """Resolve a memory's TTL in days: explicit ttl_days, else per-type, else default."""
    explicit = mem.get("ttl_days")
    if isinstance(explicit, int | float) and not isinstance(explicit, bool):
        return float(explicit)
    return float(ttl_config.get(str(mem.get("mem_type", "")), ttl_config.get("default", 0)))


def is_expired(mem: dict, now: dt.datetime, ttl_config: dict) -> bool:
    created = parse_iso(str(mem.get("created_at", "")))
    if created is None:
        return False
    return now > created + dt.timedelta(days=ttl_for(mem, ttl_config))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def jaccard(a: str, b: str) -> float:
    """Token-Jaccard similarity in [0, 1] — the offline proxy for embedding similarity."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def duplicate_pairs(memories: list[dict], threshold: float = 0.85) -> list[tuple[str, str]]:
    """Near-duplicate (id, id) pairs within the same project above the similarity threshold."""
    pairs: list[tuple[str, str]] = []
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            a, b = memories[i], memories[j]
            if not str(a.get("content", "")).strip() or not str(b.get("content", "")).strip():
                continue  # empty content is not a meaningful duplicate
            if a.get("project") == b.get("project") and jaccard(a.get("content", ""), b.get("content", "")) >= threshold:
                pairs.append((str(a.get("id")), str(b.get("id"))))
    return pairs


def is_quarantined(mem: dict) -> bool:
    """A memory is excluded from recall if quarantined, marked contradicted, or it
    declares it contradicts another memory."""
    return str(mem.get("status", "")).lower() in ("quarantined", "contradicted") or bool(mem.get("contradicts"))


def recallable(memories: list[dict], now: dt.datetime, config: dict) -> list[dict]:
    """Memories eligible for recall: not quarantined/contradicted, not expired, and
    at or above the minimum trust score."""
    min_trust = float(config.get("recall", {}).get("min_trust", 0.0))
    ttl_cfg = config.get("ttl_days", {}) or {}
    out = []
    for m in memories:
        if is_quarantined(m):
            continue
        if is_expired(m, now, ttl_cfg):
            continue
        if float(m.get("trust_score", 0) or 0) < min_trust:
            continue
        out.append(m)
    return out


def memory_health(memories: list[dict], now: dt.datetime, config: dict) -> float:
    """Decaying health score in [0, 1]: 1.0 minus a decay per stale/quarantined memory."""
    if not memories:
        return 1.0
    ttl_cfg = config.get("ttl_days", {}) or {}
    bad = sum(1 for m in memories if is_quarantined(m) or is_expired(m, now, ttl_cfg))
    decay = float(config.get("health", {}).get("decay_per_bad", 0.05))
    return max(0.0, 1.0 - decay * bad)


def explain_exclusion(mem: dict, now: dt.datetime, config: dict) -> str:
    """Plain-English reason a memory is excluded from recall, or '' if recallable —
    backs the cockpit's 'Memory Health Explanation' affordance (RFC-003 §2)."""
    if str(mem.get("status", "")).lower() in ("quarantined", "contradicted"):
        return f"quarantined (status: {mem.get('status')})"
    if mem.get("contradicts"):
        return f"contradicts {mem.get('contradicts')}"
    if is_expired(mem, now, config.get("ttl_days", {}) or {}):
        return "expired (past TTL)"
    min_trust = float(config.get("recall", {}).get("min_trust", 0.0))
    if float(mem.get("trust_score", 0) or 0) < min_trust:
        return f"trust {mem.get('trust_score')} below minimum {min_trust}"
    return ""


# ---------------------------------------------------------------------------
# Recall ranking — P21 / DAS-1490
# ---------------------------------------------------------------------------

def _recency_score(mem: dict, now: dt.datetime, half_life_days: float) -> float:
    """Half-life recency decay in [0, 1]: 1.0 for brand-new, approaching 0 as age grows.

    Formula: 2 ** (-age_days / half_life_days)
    """
    created = parse_iso(str(mem.get("created_at", "")))
    if created is None:
        return 0.0
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    return 2.0 ** (-age_days / half_life_days)


def composite_score(mem: dict, query: str, now: dt.datetime, ranking_cfg: dict) -> float:
    """Composite recall score for a single memory.

    Score = w_sim * similarity + w_recency * recency + w_importance * importance

    Components
    ----------
    similarity  — token-Jaccard(query, content): offline proxy for embedding similarity.
                  Reuses ``jaccard()``; in live ArcRift the embedding path overrides this.
    recency     — half-life decay keyed on ``created_at``; configurable ``half_life_days``.
    importance  — ``mem["importance"]`` if present (float in [0, 1]); otherwise falls
                  back to ``trust_score`` as an ordinal importance proxy.

    All three components are normalised to [0, 1] before weighting.

    Tunable via ``config["ranking"]`` (all have sensible defaults):
        ranking:
          w_sim:          0.5
          w_recency:      0.3
          w_importance:   0.2
          half_life_days: 30
    """
    w_sim = float(ranking_cfg.get("w_sim", 0.5))
    w_recency = float(ranking_cfg.get("w_recency", 0.3))
    w_importance = float(ranking_cfg.get("w_importance", 0.2))
    half_life = float(ranking_cfg.get("half_life_days", 30))

    sim = jaccard(query, str(mem.get("content", "")))
    recency = _recency_score(mem, now, half_life)
    # Prefer an explicit "importance" field; fall back to trust_score.
    raw_importance = mem.get("importance")
    if raw_importance is not None:
        importance = max(0.0, min(1.0, float(raw_importance)))
    else:
        importance = max(0.0, min(1.0, float(mem.get("trust_score", 0) or 0)))

    return w_sim * sim + w_recency * recency + w_importance * importance


def rank_memories(
    memories: list[dict],
    query: str,
    now: dt.datetime,
    config: dict,
) -> list[dict]:
    """Return *memories* ordered by composite recall score, highest first.

    This function ranks an already-eligible list (typically the output of
    ``recallable()``).  It does NOT re-apply the eligibility filter — that is
    ``recallable()``'s job.  Call them in sequence::

        eligible = recallable(all_mems, now, config)
        ranked   = rank_memories(eligible, query, now, config)

    The composite score is computed by ``composite_score()``; its three
    components (similarity, recency, importance) and weights are documented
    there and tunable via ``config["ranking"]``.
    """
    ranking_cfg = config.get("ranking", {}) or {}
    return sorted(
        memories,
        key=lambda m: composite_score(m, query, now, ranking_cfg),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Prune-hygiene callable — P21 / DAS-1490
# Schedule via WS4 HEARTBEAT; do NOT wire a live loop here.
# ---------------------------------------------------------------------------

def prune_hygiene_candidates(
    memories: list[dict],
    now: dt.datetime,
    config: dict,
) -> list[tuple[str, str]]:
    """Return ``(id, reason)`` pairs for memories that should be pruned.

    This is a **pure function** — no side effects, no ArcRift calls, no loops.
    The caller (WS4 HEARTBEAT or a CLI tool) is responsible for issuing the
    actual ``prune_memory`` calls to ArcRift.

    Pruning criteria (applied in order; first match wins):
      1. Expired — ``created_at`` is past the resolved TTL.
      2. Quarantined / contradicted — already excluded from recall.
      3. Trust below recall minimum — ineligible and unlikely to become eligible.
    """
    ttl_cfg = config.get("ttl_days", {}) or {}
    min_trust = float(config.get("recall", {}).get("min_trust", 0.0))
    candidates: list[tuple[str, str]] = []
    for m in memories:
        mid = str(m.get("id", ""))
        if is_expired(m, now, ttl_cfg):
            candidates.append((mid, "expired (past TTL)"))
        elif is_quarantined(m):
            candidates.append((mid, f"quarantined/contradicted (status: {m.get('status', 'n/a')})"))
        elif float(m.get("trust_score", 0) or 0) < min_trust:
            candidates.append((mid, f"trust {m.get('trust_score')} below recall minimum {min_trust}"))
    return candidates


# --------------------------------------------------------------------------- #
# Distillation (P20) — closing the learning loop
# --------------------------------------------------------------------------- #

#: Hard cap on `## Learned` entries per role.
MAX_LEARNED: int = 10

#: Token-Jaccard similarity threshold for clustering (lower than dedupe threshold
#: so corroborating-but-differently-worded signals are grouped together).
CLUSTER_THRESHOLD: float = 0.60


def _record_confidence(r: dict) -> float:
    """Return confidence on a 0–10 scale.

    Handles two record formats:
    - daslab-learn format: ``confidence`` key (1–10 integer).
    - ArcRift migrated format: ``trust_score`` key (0.0–1.0 float), scaled ×10.
    """
    if "confidence" in r:
        return float(r["confidence"] or 0)
    return float(r.get("trust_score", 0) or 0) * 10


def cluster_learnings(
    records: list[dict], threshold: float = CLUSTER_THRESHOLD
) -> list[list[dict]]:
    """Group records into clusters where any pair exceeds the Jaccard threshold.

    Uses a greedy single-linkage approach: a record joins the first cluster that
    has any member whose content similarity is >= *threshold*.  Reuses the
    existing :func:`jaccard` token-overlap proxy so the offline test path is
    deterministic without a live embedding model.

    The deny-boundary check is the caller's responsibility — only records that
    have already passed the boundary filter should be passed here.
    """
    clusters: list[list[dict]] = []
    for rec in records:
        placed = False
        rec_content = str(rec.get("content", rec.get("insight", "")))
        for cluster in clusters:
            for member in cluster:
                member_content = str(member.get("content", member.get("insight", "")))
                if jaccard(rec_content, member_content) >= threshold:
                    cluster.append(rec)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([rec])
    return clusters


def merge_cluster(cluster: list[dict]) -> dict:
    """Merge a cluster of related learnings into a single higher-confidence insight.

    Rules:
    - Base insight: the highest-confidence record (tie-broken by most-recent date).
    - Confidence boost: +1 per corroborating record beyond the first, capped at 10.
    - Date: most recent among the cluster members.
    - Scope: narrowest scope wins (project-scoped beats org-scoped so org promotion
      still requires a manager gate).
    - ``source_count``: number of records merged (audit trail).
    """
    if not cluster:
        raise ValueError("Cannot merge an empty cluster")

    # Sort by confidence desc, then date desc as tie-breaker.
    sorted_cluster = sorted(
        cluster,
        key=lambda r: (-_record_confidence(r), str(r.get("date", r.get("created_at", "")))),
    )
    base = dict(sorted_cluster[0])  # shallow copy — we will mutate it

    # Confidence boost: +1 per corroborating record, cap at 10.
    raw_conf = _record_confidence(base) + (len(cluster) - 1)
    base["confidence"] = min(10, int(raw_conf)) if raw_conf == int(raw_conf) else min(10.0, raw_conf)

    # Most recent date (checking both daslab-learn and ArcRift date fields).
    date_fields = [
        str(r.get("date", r.get("created_at", ""))) for r in cluster
    ]
    valid_dates = [d for d in date_fields if d]
    if valid_dates:
        base["date"] = max(valid_dates)

    # Narrowest scope: if any record is project-scoped, keep project scope.
    scopes = [str(r.get("scope", "org")) for r in cluster]
    non_org = [s for s in scopes if s != "org"]
    if non_org:
        base["scope"] = max(set(non_org), key=non_org.count)

    base["source_count"] = len(cluster)
    return base


def distill_learnings(
    records: list[dict],
    project: str,
    deny_projects: list[str] | None = None,
    bound: int = MAX_LEARNED,
    cluster_threshold: float = CLUSTER_THRESHOLD,
) -> list[dict]:
    """Full distillation pipeline for a single role.

    Steps:
    1. **Filter** — keep only records whose project scope matches *project* or
       ``"org"``, excluding any record from a ``deny_projects`` project.  This
       enforces the workstream deny-boundary: distillation never moves a learning
       across it.
    2. **Cluster** — group semantically similar learnings via
       :func:`cluster_learnings` (token-Jaccard, *cluster_threshold*).
    3. **Merge** — collapse each cluster into one higher-confidence insight via
       :func:`merge_cluster`.
    4. **Sort** — by confidence descending, then date descending (most recent
       first within the same confidence tier).
    5. **Bound** — return the top *bound* entries only (hard cap = ``MAX_LEARNED``).

    Returns an empty list when no eligible records exist.
    """
    deny = set(deny_projects or [])

    # Step 1: filter — include same-project records and org-tier records,
    # but always exclude records from deny-listed projects.
    filtered: list[dict] = []
    for r in records:
        r_project = str(r.get("project", r.get("scope", "")))
        if r_project in deny:
            continue
        if r_project == project or r_project == "org":
            filtered.append(r)

    if not filtered:
        return []

    # Steps 2–3: cluster then merge.
    clusters = cluster_learnings(filtered, threshold=cluster_threshold)
    merged = [merge_cluster(c) for c in clusters]

    # Step 4: sort — confidence desc, date desc.
    merged.sort(
        key=lambda r: (-_record_confidence(r), str(r.get("date", r.get("created_at", "")))),
    )

    # Step 5: bound.
    return merged[:bound]


def is_org_promotion(record: dict) -> bool:
    """Return True if *record* is a project-scoped insight being promoted to org tier.

    A promotion is detected by the presence of a ``promoted_from`` field (the
    originating project scope) on a record whose current ``scope`` is ``"org"``.
    """
    return (
        str(record.get("scope", "")) == "org"
        and bool(record.get("promoted_from"))
    )


def needs_manager_gate(record: dict) -> bool:
    """Return True if *record* requires manager approval before being written to org scope.

    Per the daslab-learn hard rule: *only a manager writes to the org tier.*
    A distillation agent that is not a manager must leave such insights at
    project scope and log an escalation instead of promoting them.
    """
    return is_org_promotion(record)


def format_learned_section(
    distilled: list[dict],
    date: str,
    bound: int = MAX_LEARNED,
) -> str:
    """Render the ``## Learned`` markdown section for insertion into an AGENTS.md template.

    Format::

        ## Learned
        <!-- DISTILLATION — generated by daslab-learn P20 on DATE. Bounded at N.
             Do not edit — re-run distillation. -->
        - **DATE** `key` (confidence: N/10, scope: SCOPE): insight text.

    If *distilled* is empty, a placeholder line is emitted so the section is
    visibly present (not silently absent).
    """
    banner = (
        f"<!-- DISTILLATION — generated by daslab-learn P20 on {date}. "
        f"Bounded at {bound}. Do not edit — re-run distillation. -->"
    )
    lines = ["## Learned", banner]
    for r in distilled:
        key = str(r.get("key", r.get("id", "unknown")))
        conf = r.get("confidence", r.get("trust_score", "?"))
        scope = str(r.get("scope", "project"))
        item_date = str(r.get("date", r.get("created_at", date)))[:10]
        content = str(r.get("content", r.get("insight", "")))
        lines.append(
            f"- **{item_date}** `{key}` (confidence: {conf}/10, scope: {scope}): {content}"
        )
    if not distilled:
        lines.append("_(no distilled learnings yet)_")
    return "\n".join(lines)


def apply_learned_to_template(
    template_text: str,
    distilled: list[dict],
    date: str,
    bound: int = MAX_LEARNED,
) -> str:
    """Upsert the ``## Learned`` section into an AGENTS.md template string.

    - If a ``## Learned`` section already exists, it is replaced in-place
      (from the ``## Learned`` header up to, but not including, the next
      ``## `` heading — or end-of-file).
    - If no such section exists, the new section is appended at the end.

    Returns the updated template text.  Does NOT write to disk — the caller
    is responsible for persisting the result.
    """
    new_section = format_learned_section(distilled, date, bound)
    header = "## Learned\n"

    if header in template_text:
        idx = template_text.index(header)
        # Find the end of the existing section: next ## heading or EOF.
        rest = template_text[idx + len(header):]
        next_match = re.search(r"^## ", rest, re.M)
        end_idx = idx + len(header) + next_match.start() if next_match else len(template_text)
        updated = template_text[:idx] + new_section + "\n" + template_text[end_idx:]
    else:
        # Append after a blank separator line.
        sep = "\n" if template_text.endswith("\n") else "\n\n"
        updated = template_text + sep + new_section + "\n"

    return updated
