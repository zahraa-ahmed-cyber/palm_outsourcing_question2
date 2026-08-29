"""Load the two CSVs. Dates stay as date objects; blank end dates stay None."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return date.fromisoformat(value)


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_billing(path: Path) -> list[dict]:
    rows = []
    for raw in load_csv(path):
        rows.append(
            {
                "client_name": raw["client_name"].strip(),
                "retainer_start": parse_date(raw.get("retainer_start", "")),
                "retainer_end": parse_date(raw.get("retainer_end", "")),
                "monthly_retainer_usd": int(raw["monthly_retainer_usd"]),
                "package": raw.get("package", "").strip(),
                "account_lead": raw.get("account_lead", "").strip(),
                "billing_contact": raw.get("billing_contact", "").strip(),
            }
        )
    return rows


def load_projects(path: Path) -> list[dict]:
    rows = []
    for raw in load_csv(path):
        rows.append(
            {
                "brand_name": raw["brand_name"].strip(),
                "current_scope": raw.get("current_scope", "").strip(),
                "last_delivery": parse_date(raw.get("last_delivery", "")),
                "deliveries_this_term": int(raw.get("deliveries_this_term") or 0),
                "health": raw.get("health", "").strip(),
                "account_lead": raw.get("account_lead", "").strip(),
                "notes": raw.get("notes", "").strip(),
            }
        )
    return rows
