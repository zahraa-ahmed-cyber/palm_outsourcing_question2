"""Copy the runtime app into docs/ — matching happens in the browser."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build() -> Path:
    docs = ROOT / "docs"
    data_out = docs / "data"
    docs.mkdir(exist_ok=True)
    data_out.mkdir(exist_ok=True)

    billing = (ROOT / "data" / "billing_export.csv").read_text(encoding="utf-8")
    project = (ROOT / "data" / "project_export.csv").read_text(encoding="utf-8")
    (data_out / "billing_export.csv").write_text(billing, encoding="utf-8")
    (data_out / "project_export.csv").write_text(project, encoding="utf-8")

    shutil.copyfile(ROOT / "web" / "radar.js", docs / "radar.js")

    html = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    html = html.replace("/*__SAMPLE_BILLING__*/", json.dumps(billing))
    html = html.replace("/*__SAMPLE_PROJECT__*/", json.dumps(project))
    out = docs / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build())
