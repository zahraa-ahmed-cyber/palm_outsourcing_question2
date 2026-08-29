# Relay — Renewal Radar

Working screen for Harbourline account leads: two messy exports in, the next 45 days of retainers out. No terminal, no new logins, no paid APIs.

**Running version:** _pending public GitHub Pages URL — see below if this line still says pending._

Open `docs/index.html` (or this repo’s GitHub Pages) . As-of date is frozen at **29 Aug 2026** so the sample window does not rot.

---

## What you are looking at

Harbourline runs rolling three-month retainers. Renewal dates live in a billing export. Scope and delivery live in a project export. The files share **no client ID**, names disagree, some end dates are blank, and re-signs leave duplicate rows. Two brands lapsed last quarter because nobody clocked the date.

This build:

1. Loads `data/billing_export.csv` (14 rows) and `data/project_export.csv` (12 rows).
2. Normalises names, collapses re-signs, infers missing ends, matches the two files.
3. Writes a static page an account lead can filter by book and search.

```
python -m pip install -r requirements.txt
python -m pytest
python -m radar.build          # regenerates docs/index.html
python -m http.server 8765 -d docs
```

---

## What it does with each data problem

### 1. No shared client ID — names disagree

Billing uses legal names (`THE KINDRED HOME INC.`, `Bloom & Co Beauty`). The project tool uses trading names (`Kindred Home`, `Bloom and Co. Beauty`).

**What the build does:** strip case, punctuation, leading *The*, and legal suffixes (`LLC`, `Ltd`, `Inc`, `Co`). Treat `&` as `and`. If the letters match once spaces are gone, that is a match (`Northstar Coffee` / `North Star Coffee`, `Glow Theory` / `GlowTheory`). A trailing extra word (`Mira Skin` / `Mira Skin Care`) still auto-matches, at 90 rather than 100.

**What I tested:** `test_legal_suffix_and_casing_match`, `test_ampersand_vs_and`, `test_leading_the_and_inc`, `test_split_compound_name`, `test_extra_word_still_auto_matches`, `test_unrelated_names_stay_unmatched`. Unrelated pair `Woven Home` / `Solace Apothecary` stays below the floor.

Unmatched rows are **not dropped**. Woven Home still appears on the 45-day list with a “no project match” chip. Solace sits under **Needs a look** — a brand in delivery with no billing row is how a signature misses the invoice file.

### 2. Some retainers have no end date

Bloom and Velvet Hour have a start and a blank end.

**What the build does:** infer `start + 3 calendar months` (Jun 20 → Sep 20, not +90 days) and flag the card **end date inferred**. Alternative I did not take: hide the row until billing fills it. That is last quarter’s lapse.

**What I tested:** `test_missing_end_date_is_three_calendar_months`.

### 3. Clients appear twice after re-signing

Acme Wellness LLC and Northstar Coffee Co. each have an old closed term and a current term.

**What the build does:** group on the normalised name, keep the **latest start** as current, hang prior terms on the card (`re-signed · prior term ended …`). Alternative I did not take: latest *end* date — wrong when the new term has no end yet.

**What I tested:** `test_re_sign_keeps_latest_start_only`. Acme’s radar card is the Jun 2026 term at $6,500, not the expired $5,500 term.

### 4. Inside vs outside the 45-day window

As of 29 Aug 2026 the window ends 13 Oct.

| Brand | End | Where it lands |
| --- | --- | --- |
| Mira Skin | 8 Sep | upcoming (10 days) |
| Pebble Pets | 20 Nov | later |
| Oak & Iron | 15 Dec | later |
| Glow Theory | 20 Aug | **already lapsed** (9 days ago) |

Nadia asked for the next 45 days. The lapsed tab is extra, on purpose: that is the failure mode. It only shows terms that ended in the last 60 days so old closed retainers (already collapsed) do not haunt the board.

**What I tested:** `test_window_contains_inside_and_excludes_outside`, `test_lapsed_retainer_is_not_dumped_in_upcoming`.

---

## Judgement calls (also in the code)

They live as comments next to the code, not as a syntax tour.

| Call | Why |
| --- | --- |
| Calendar months, not 90 days | That is how a three-month retainer is sold. |
| Latest *start* wins a re-sign | The new term is the one operations cares about. |
| Show inferred dates instead of dropping them | Blank end date is how brands lapse. |
| Keep unmatched billing on the radar | No project row is not a reason to hide a renewal. |
| Prefer the project (trading) name on the card | That is the name the lead uses in Slack. |
| Show recent lapses even though Nadia asked for 45 days ahead | Last quarter the date had already passed. |
| Stdlib `difflib`, not a paid matcher | Spec: no paid APIs. |
| Freeze as-of at 29 Aug 2026 | A demo that depends on “today” is stale next month. |

Auto-match threshold is 88. Review band is 72–87 (attach, but flag). Below 72 is unmatched.

---

## Sample data

Both files are intentionally messy. 26 rows across the two CSVs.

- **Billing** `data/billing_export.csv` — 14 rows, 12 current retainers after collapsing two re-signs, two blank ends.
- **Project** `data/project_export.csv` — 12 rows, one unmatched (`Solace Apothecary`).

---

## Repo layout

```
data/           sample exports
radar/          matching + windowing (judgement comments in names.py, pipeline.py)
tests/          the data problems, not the helpers
web/            HTML template
docs/           built page (this is the running version)
```
