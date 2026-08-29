"""Tests are about the data problems, not the helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from radar.io import load_billing, load_projects
from radar.names import name_score, normalize_name
from radar.pipeline import collapse_resigns, infer_end, run_radar

ROOT = Path(__file__).resolve().parent.parent
AS_OF = date(2026, 8, 29)


def _radar():
    return run_radar(
        load_billing(ROOT / "data" / "billing_export.csv"),
        load_projects(ROOT / "data" / "project_export.csv"),
        AS_OF,
    )


def test_legal_suffix_and_casing_match():
    score, why = name_score("Acme Wellness LLC", "ACME Wellness")
    assert score == 100
    assert "legal suffix" in why


def test_ampersand_vs_and():
    score, _ = name_score("Bloom & Co Beauty", "Bloom and Co. Beauty")
    assert score == 100


def test_leading_the_and_inc():
    score, _ = name_score("THE KINDRED HOME INC.", "Kindred Home")
    assert score == 100
    assert normalize_name("THE KINDRED HOME INC.") == "kindred home"


def test_split_compound_name():
    score, why = name_score("Northstar Coffee Co.", "North Star Coffee")
    assert score >= 96
    assert "spaces" in why
    assert "Northstar" not in why


def test_extra_word_is_possible_not_confirmed():
    score, _ = name_score("Mira Skin", "Mira Skin Care")
    assert score == 90
    from radar.names import classify_score

    assert classify_score(90) == "review"
    radar = _radar()
    mira = next(r for r in radar["upcoming"] if r["billing_name"] == "Mira Skin")
    assert mira["match_kind"] == "review"
    assert mira["display_name"] == "Mira Skin"
    assert mira["scope"] is None
    assert mira["possible_match"]["project_name"] == "Mira Skin Care"
    assert mira["possible_match"]["score"] == 90


def test_confirmed_match_still_uses_trading_name():
    radar = _radar()
    acme = next(r for r in radar["upcoming"] if "Acme" in r["billing_name"])
    assert acme["match_kind"] == "matched"
    assert acme["display_name"] == "ACME Wellness"
    assert acme["scope"]


def test_unrelated_names_stay_unmatched():
    score, _ = name_score("Woven Home Co.", "Solace Apothecary")
    assert score < 72


def test_re_sign_keeps_latest_start_only():
    billing = load_billing(ROOT / "data" / "billing_export.csv")
    current, superseded = collapse_resigns(billing)
    acme = [r for r in current if "acme" in r["client_name"].casefold()]
    assert len(acme) == 1
    assert acme[0]["retainer_start"] == date(2026, 6, 15)
    assert acme[0]["retainer_end"] == date(2026, 9, 15)
    assert len(acme[0]["prior_terms"]) == 1
    assert any(s["client_name"] == "Acme Wellness LLC" for s in superseded)


def test_missing_end_date_is_three_calendar_months():
    assert infer_end(date(2026, 6, 20)) == date(2026, 9, 20)
    radar = _radar()
    bloom = next(r for r in radar["upcoming"] if "Bloom" in r["billing_name"])
    assert bloom["end_inferred"] is True
    assert bloom["end"] == "2026-09-20"


def test_window_contains_inside_and_excludes_outside():
    radar = _radar()
    names = {r["billing_name"] for r in radar["upcoming"]}
    assert "Mira Skin" in names  # 8 Sep — 10 days
    assert "Northstar Coffee Co." in names  # 30 Sep
    assert "Pebble Pets Ltd" not in names  # 20 Nov, outside 45 days
    assert "Oak & Iron Outfitters LLC" not in names  # 15 Dec


def test_lapsed_retainer_is_not_dumped_in_upcoming():
    radar = _radar()
    upcoming = {r["billing_name"] for r in radar["upcoming"]}
    lapsed = {r["billing_name"] for r in radar["lapsed"]}
    assert "Glow Theory" not in upcoming
    assert "Glow Theory" in lapsed


def test_unmatched_rows_surface_on_both_sides():
    radar = _radar()
    assert "Woven Home Co." in radar["unmatched_billing"]
    assert "Solace Apothecary" in radar["unmatched_projects"]
    # Woven still appears on the radar — no project row is not a reason
    # to hide a renewal date.
    woven = next(r for r in radar["upcoming"] if r["billing_name"] == "Woven Home Co.")
    assert woven["scope"] is None


def test_sample_shape_is_genuinely_messy():
    billing = load_billing(ROOT / "data" / "billing_export.csv")
    projects = load_projects(ROOT / "data" / "project_export.csv")
    assert len(billing) + len(projects) >= 12
    assert any(r["retainer_end"] is None for r in billing)
    names = [r["client_name"] for r in billing]
    assert names.count("Acme Wellness LLC") == 2
