# Relay — Renewal Radar

Working screen for Harbourline account leads: pull both exports, see the next 45 days. No terminal, no new logins, no paid APIs.

**Running version:** open [docs/index.html](docs/index.html) locally via `python -m http.server 8765 -d docs`, then [http://127.0.0.1:8765/](http://127.0.0.1:8765/).

A public GitHub Pages URL goes here after `gh auth login` and `gh repo create` — this machine is not logged into GitHub yet. Pages must serve the `docs/` folder (it includes `data/*.csv` so **Load latest exports** works).

The page **processes the CSVs in the browser**. Next month Nadia drops two new files → **upload them** (or replace `data/*.csv` and click **Load latest exports**). Nobody runs Python to see the radar.

---

## How an account lead uses it

1. Open the page.
2. It loads `data/billing_export.csv` and `data/project_export.csv` (the files Relay already has).
3. Or: **Billing export** + **Project export** → **Show radar**.
4. Filter by book, search a brand, change **As of** if needed.

Sample exports are dated around August 2026. The as-of date defaults to **29 Aug 2026** so the demo window does not rot. Set it to today when you load a live export.

---

## What it does with each data problem

### 1. No shared client ID — names disagree

Billing uses legal names (`THE KINDRED HOME INC.`, `Bloom & Co Beauty`). The project tool uses trading names (`Kindred Home`, `Bloom and Co. Beauty`).

**What the build does:** strip case, punctuation, leading *The*, and legal suffixes. Treat `&` as `and`. **Confirmed** only when names are the same after that (score 100). Anything 72–99 is a **possible match — confirm**, shown in a dashed box, not treated as the same client. `Mira Skin` / `Mira Skin Care` (90) is possible, not confirmed. Unrelated names stay unmatched.

**What I tested:** `test_legal_suffix_and_casing_match`, `test_ampersand_vs_and`, `test_leading_the_and_inc`, `test_split_compound_name`, `test_extra_word_is_possible_not_confirmed`, `test_confirmed_match_still_uses_trading_name`, `test_unrelated_names_stay_unmatched`.

Unmatched billing (`Woven Home Co.`) still appears on the 45-day list. Unmatched project (`Solace Apothecary`) sits under **Needs a look**.

### 2. Some retainers have no end date

Bloom and Velvet Hour have a start and a blank end.

**What the build does:** estimate `start + 3 calendar months` (Jun 20 → Sep 20) and label the card **Estimated renewal — verify**. Alternative I did not take: hide the row. That is last quarter’s lapse.

**What I tested:** `test_missing_end_date_is_three_calendar_months`.

### 3. Clients appear twice after re-signing

Acme Wellness LLC and Northstar Coffee Co. each have an old closed term and a current term.

**What the build does:** group on the normalised name, keep the **latest start** as current. Alternative I did not take: latest *end* date — wrong when the new term has no end yet.

**What I tested:** `test_re_sign_keeps_latest_start_only`.

### 4. Inside vs outside the 45-day window

As of 29 Aug 2026 the window ends 13 Oct.

| Brand | End | Where it lands |
| --- | --- | --- |
| Mira Skin | 8 Sep | upcoming (10 days) |
| Pebble Pets | 20 Nov | later |
| Oak & Iron | 15 Dec | later |
| Glow Theory | 20 Aug | **already lapsed** (9 days ago) |

The lapsed tab is extra, on purpose: last quarter the date had already passed.

**What I tested:** `test_window_contains_inside_and_excludes_outside`, `test_lapsed_retainer_is_not_dumped_in_upcoming`.

---

## Judgement calls (also in the code)

| Call | Why |
| --- | --- |
| Process CSVs in the browser | The account lead will not run `python -m radar.build`. |
| Confirmed match = 100 only | A 90% name hit must not look like the same client. |
| Calendar months, not 90 days | That is how a three-month retainer is sold. |
| Latest *start* wins a re-sign | The new term is the one operations cares about. |
| Show estimated dates instead of dropping them | Blank end date is how brands lapse. |
| Keep unmatched billing on the radar | No project row is not a reason to hide a renewal. |
| Show recent lapses even though Nadia asked for 45 days ahead | Last quarter the date had already passed. |
| Stdlib / in-page matching, not a paid API | Spec: no paid APIs. |

Python (`radar/`) is the tested spec of those rules. `web/radar.js` is the same rules for the running page. `python -m pytest` is how I know the spec holds.

```
python -m pip install -r requirements.txt
python -m pytest
python -m radar.build          # copies the app + CSVs into docs/
python -m http.server 8765 -d docs
```

---

## Sample data

26 rows across the two CSVs, intentionally messy.

- **Billing** `data/billing_export.csv` — 14 rows, 12 current retainers after collapsing two re-signs, two blank ends.
- **Project** `data/project_export.csv` — 12 rows, one unmatched (`Solace Apothecary`).

---

## Repo layout

```
data/           sample exports
radar/          Python spec of matching (judgement comments; tests)
web/            browser app (radar.js + page)
docs/           running version (HTML + JS + copies of the CSVs)
tests/
```
