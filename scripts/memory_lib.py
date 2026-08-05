#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import re


def parse_iso(ts: str) -> dt.datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(ts, fmt)
        except (ValueError, TypeError):
            continue
    return None


def trust_for(provenance: str, tiers: dict) -> float:
    return float(tiers.get(str(provenance), tiers.get("unverified_claim", 0.0)))


def ttl_for(mem: dict, ttl_config: dict) -> float:
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
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def duplicate_pairs(memories: list[dict], threshold: float = 0.85) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            a, b = memories[i], memories[j]
            if not str(a.get("content", "")).strip() or not str(b.get("content", "")).strip():
                continue
            if a.get("project") == b.get("project") and jaccard(a.get("content", ""), b.get("content", "")) >= threshold:
                pairs.append((str(a.get("id")), str(b.get("id"))))
    return pairs


def is_quarantined(mem: dict) -> bool:
    return str(mem.get("status", "")).lower() in ("quarantined", "contradicted") or bool(mem.get("contradicts"))


def recallable(memories: list[dict], now: dt.datetime, config: dict) -> list[dict]:
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
    if not memories:
        return 1.0
    ttl_cfg = config.get("ttl_days", {}) or {}
    bad = sum(1 for m in memories if is_quarantined(m) or is_expired(m, now, ttl_cfg))
    decay = float(config.get("health", {}).get("decay_per_bad", 0.05))
    return max(0.0, 1.0 - decay * bad)


def explain_exclusion(mem: dict, now: dt.datetime, config: dict) -> str:
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


def _recency_score(mem: dict, now: dt.datetime, half_life_days: float) -> float:
    created = parse_iso(str(mem.get("created_at", "")))
    if created is None:
        return 0.0
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    return 2.0 ** (-age_days / half_life_days)


def composite_score(mem: dict, query: str, now: dt.datetime, ranking_cfg: dict) -> float:
    w_sim = float(ranking_cfg.get("w_sim", 0.5))
    w_recency = float(ranking_cfg.get("w_recency", 0.3))
    w_importance = float(ranking_cfg.get("w_importance", 0.2))
    half_life = float(ranking_cfg.get("half_life_days", 30))

    sim = jaccard(query, str(mem.get("content", "")))
    recency = _recency_score(mem, now, half_life)

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
    ranking_cfg = config.get("ranking", {}) or {}
    return sorted(
        memories,
        key=lambda m: composite_score(m, query, now, ranking_cfg),
        reverse=True,
    )


def prune_hygiene_candidates(
    memories: list[dict],
    now: dt.datetime,
    config: dict,
) -> list[tuple[str, str]]:
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


MAX_LEARNED: int = 10


CLUSTER_THRESHOLD: float = 0.60


def _record_confidence(r: dict) -> float:
    if "confidence" in r:
        return float(r["confidence"] or 0)
    return float(r.get("trust_score", 0) or 0) * 10


def cluster_learnings(
    records: list[dict], threshold: float = CLUSTER_THRESHOLD
) -> list[list[dict]]:
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
    if not cluster:
        raise ValueError("Cannot merge an empty cluster")


    sorted_cluster = sorted(
        cluster,
        key=lambda r: (-_record_confidence(r), str(r.get("date", r.get("created_at", "")))),
    )
    base = dict(sorted_cluster[0])


    raw_conf = _record_confidence(base) + (len(cluster) - 1)
    base["confidence"] = min(10, int(raw_conf)) if raw_conf == int(raw_conf) else min(10.0, raw_conf)


    date_fields = [
        str(r.get("date", r.get("created_at", ""))) for r in cluster
    ]
    valid_dates = [d for d in date_fields if d]
    if valid_dates:
        base["date"] = max(valid_dates)


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
    deny = set(deny_projects or [])


    filtered: list[dict] = []
    for r in records:
        r_project = str(r.get("project", r.get("scope", "")))
        if r_project in deny:
            continue
        if r_project == project or r_project == "org":
            filtered.append(r)

    if not filtered:
        return []


    clusters = cluster_learnings(filtered, threshold=cluster_threshold)
    merged = [merge_cluster(c) for c in clusters]


    merged.sort(
        key=lambda r: (-_record_confidence(r), str(r.get("date", r.get("created_at", "")))),
    )


    return merged[:bound]


def is_org_promotion(record: dict) -> bool:
    return (
        str(record.get("scope", "")) == "org"
        and bool(record.get("promoted_from"))
    )


def needs_manager_gate(record: dict) -> bool:
    return is_org_promotion(record)


def format_learned_section(
    distilled: list[dict],
    date: str,
    bound: int = MAX_LEARNED,
) -> str:
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
    new_section = format_learned_section(distilled, date, bound)
    header = "## Learned\n"

    if header in template_text:
        idx = template_text.index(header)

        rest = template_text[idx + len(header):]
        next_match = re.search(r"^## ", rest, re.M)
        end_idx = idx + len(header) + next_match.start() if next_match else len(template_text)
        updated = template_text[:idx] + new_section + "\n" + template_text[end_idx:]
    else:

        sep = "\n" if template_text.endswith("\n") else "\n\n"
        updated = template_text + sep + new_section + "\n"

    return updated
