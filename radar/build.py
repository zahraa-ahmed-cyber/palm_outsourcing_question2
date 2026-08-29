"""Build a self-contained HTML file an account lead can open."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar.io import load_billing, load_projects
from radar.pipeline import run_radar

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AS_OF = date(2026, 8, 29)


def build(as_of: date = DEFAULT_AS_OF) -> Path:
    billing = load_billing(ROOT / "data" / "billing_export.csv")
    projects = load_projects(ROOT / "data" / "project_export.csv")
    payload = run_radar(billing, projects, as_of)

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "radar.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    template = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    html = template.replace(
        "/*__RADAR_JSON__*/",
        json.dumps(payload, ensure_ascii=False),
    )
    out = docs / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(path)
