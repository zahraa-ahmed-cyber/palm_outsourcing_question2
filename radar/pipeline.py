"""Turn two messy exports into a 45-day renewal list.

Harbourline's retainers are rolling three-month. The 45-day window is
Nadia's spec. Everything else in here is a judgement call called out
in comments.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from radar.names import classify_score, compact, name_score, normalize_name

WINDOW_DAYS = 45


def infer_end(start: date | None) -> date | None:
    """Missing end date → start plus three calendar months.

    Alternative: start + 90 days. That is not how a Jun 20 retainer is
    sold ('three months' means 20 Sep, not 18 Sep). Alternative: drop
    the row. That recreates last quarter's lapse — the date was missing
    so nobody looked.
    """
    if start is None:
        return None
    month = start.month - 1 + 3
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def collapse_resigns(billing: list[dict]) -> tuple[list[dict], list[dict]]:
    """A client who re-signed appears twice. Keep the latest start.

    Alternative: keep the latest end date. Wrong when an old closed
    term has a later-looking leftover date, and wrong when the new term
    has no end date yet. Latest start is the row that means 'current'.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in billing:
        key = normalize_name(row["client_name"]) or compact(row["client_name"])
        groups[key].append(row)

    current: list[dict] = []
    superseded: list[dict] = []
    for key, rows in groups.items():
        ordered = sorted(
            rows,
            key=lambda r: r["retainer_start"] or date.min,
            reverse=True,
        )
        winner = dict(ordered[0])
        winner["normalized"] = key
        winner["prior_terms"] = [
            {
                "start": r["retainer_start"].isoformat() if r["retainer_start"] else None,
                "end": r["retainer_end"].isoformat() if r["retainer_end"] else None,
                "monthly_retainer_usd": r["monthly_retainer_usd"],
            }
            for r in ordered[1:]
        ]
        current.append(winner)
        for r in ordered[1:]:
            old = dict(r)
            old["normalized"] = key
            old["superseded_by_start"] = (
                winner["retainer_start"].isoformat() if winner["retainer_start"] else None
            )
            superseded.append(old)
    return current, superseded


def pair_projects(
    current: list[dict], projects: list[dict]
) -> tuple[dict[int, tuple[int, int, str]], list[dict], list[str], list[str]]:
    """Greedy one-to-one match, highest score first.

    Alternative: every billing row independently takes its best project
    row. Then two legal-name variants steal the same project record.
    We already collapsed re-signs, so unique-match is the honest model.
    """
    scored: list[tuple[int, int, int, str]] = []
    for bi, b in enumerate(current):
        for pi, p in enumerate(projects):
            score, why = name_score(b["client_name"], p["brand_name"])
            scored.append((score, bi, pi, why))
    scored.sort(key=lambda t: t[0], reverse=True)

    used_b: set[int] = set()
    used_p: set[int] = set()
    attached: dict[int, tuple[int, int, str]] = {}
    reviews: list[dict] = []

    for score, bi, pi, why in scored:
        kind = classify_score(score)
        if kind == "unmatched":
            continue
        if bi in used_b or pi in used_p:
            continue
        if kind == "review":
            reviews.append(
                {
                    "billing_name": current[bi]["client_name"],
                    "project_name": projects[pi]["brand_name"],
                    "score": score,
                    "why": why,
                }
            )
            # Still attach so the lead sees scope next to the date —
            # but the row is flagged. Alternative: leave unmatched until
            # a human confirms. That hides the renewal.
            used_b.add(bi)
            used_p.add(pi)
            attached[bi] = (pi, score, why)
            continue
        used_b.add(bi)
        used_p.add(pi)
        attached[bi] = (pi, score, why)

    unmatched_billing = [current[i]["client_name"] for i in range(len(current)) if i not in used_b]
    unmatched_projects = [projects[i]["brand_name"] for i in range(len(projects)) if i not in used_p]
    return attached, reviews, unmatched_billing, unmatched_projects


def bucket(end: date | None, as_of: date) -> str:
    if end is None:
        return "no_date"
    window_end = as_of + timedelta(days=WINDOW_DAYS)
    if end < as_of:
        return "lapsed"
    if end <= window_end:
        return "upcoming"
    return "later"


def run_radar(
    billing: list[dict],
    projects: list[dict],
    as_of: date,
) -> dict:
    current, superseded = collapse_resigns(billing)
    attached, reviews, unmatched_b, unmatched_p = pair_projects(current, projects)

    records = []
    missing_end = []
    for bi, b in enumerate(current):
        inferred = False
        end = b["retainer_end"]
        if end is None:
            end = infer_end(b["retainer_start"])
            inferred = True
            missing_end.append(b["client_name"])

        project = None
        score = None
        why = None
        if bi in attached:
            pi, score, why = attached[bi]
            project = projects[pi]

        status = bucket(end, as_of)
        days = (end - as_of).days if end else None

        display = (
            project["brand_name"]
            if project and score and score >= 88
            else b["client_name"]
        )
        # Prefer the project (trading) name on the card — that is what
        # the lead uses in Slack. Alternative: always show the billing
        # legal name. Accurate, and they will not recognise half of them.

        records.append(
            {
                "display_name": display,
                "billing_name": b["client_name"],
                "project_name": project["brand_name"] if project else None,
                "match_score": score,
                "match_why": why,
                "match_kind": classify_score(score or 0) if score is not None else "unmatched",
                "start": b["retainer_start"].isoformat() if b["retainer_start"] else None,
                "end": end.isoformat() if end else None,
                "end_inferred": inferred,
                "days": days,
                "status": status,
                "monthly_retainer_usd": b["monthly_retainer_usd"],
                "package": b["package"],
                "account_lead": (project["account_lead"] if project else b["account_lead"]),
                "scope": project["current_scope"] if project else None,
                "last_delivery": project["last_delivery"].isoformat()
                if project and project["last_delivery"]
                else None,
                "deliveries_this_term": project["deliveries_this_term"] if project else None,
                "health": project["health"] if project else None,
                "notes": project["notes"] if project else None,
                "prior_terms": b.get("prior_terms") or [],
                "billing_contact": b["billing_contact"],
            }
        )

    def sort_key(r: dict):
        return (r["days"] is None, r["days"] if r["days"] is not None else 10_000)

    upcoming = sorted([r for r in records if r["status"] == "upcoming"], key=sort_key)
    lapsed = sorted([r for r in records if r["status"] == "lapsed"], key=sort_key)
    later = sorted([r for r in records if r["status"] == "later"], key=sort_key)
    no_date = [r for r in records if r["status"] == "no_date"]

    # Lapsed is not in Nadia's 45-day ask. Showing it anyway is the
    # whole point of last quarter: the date had already passed. Capped
    # to retainers that ended in the last 60 days so old closed terms
    # (already collapsed) do not haunt the board.
    recent_lapsed = [r for r in lapsed if r["days"] is not None and r["days"] >= -60]

    return {
        "as_of": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "window_end": (as_of + timedelta(days=WINDOW_DAYS)).isoformat(),
        "upcoming": upcoming,
        "lapsed": recent_lapsed,
        "later": later,
        "no_date": no_date,
        "records": records,
        "needs_review": reviews,
        "unmatched_billing": unmatched_b,
        "unmatched_projects": unmatched_p,
        "superseded": [
            {
                "client_name": r["client_name"],
                "start": r["retainer_start"].isoformat() if r["retainer_start"] else None,
                "end": r["retainer_end"].isoformat() if r["retainer_end"] else None,
                "superseded_by_start": r["superseded_by_start"],
            }
            for r in superseded
        ],
        "missing_end_dates": missing_end,
        "counts": {
            "billing_rows": len(billing),
            "project_rows": len(projects),
            "current_retainers": len(current),
            "upcoming": len(upcoming),
            "lapsed": len(recent_lapsed),
            "later": len(later),
        },
    }
