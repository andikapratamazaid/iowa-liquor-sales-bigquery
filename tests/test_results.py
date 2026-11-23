"""
Validation tests for the computed result tables in data/results.

These tests check the published aggregates for internal consistency:
totals reconcile across independent breakdowns, shares sum to 100 percent,
no impossible values appear, and the time coverage matches the official
dataset (January 2012 onward).

Run from the project root:  python3 -m pytest tests/ -q
"""

import os

import pandas as pd
import pytest

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "results")


def load(name):
    return pd.read_csv(os.path.join(RESULTS, name))


@pytest.fixture(scope="module")
def overview():
    return load("overview.csv").iloc[0]


def test_overview_scale(overview):
    # The official dataset holds tens of millions of invoice lines.
    assert overview["total_rows"] > 20_000_000
    assert overview["total_sale_dollars"] > 1_000_000_000
    assert overview["distinct_stores"] > 500
    assert overview["distinct_counties"] >= 90


def test_date_range(overview):
    first = pd.Timestamp(overview["first_date"])
    last = pd.Timestamp(overview["last_date"])
    assert first.year == 2012 and first.month == 1
    assert last.year >= 2025
    assert last > first


def test_yearly_reconciles_with_overview(overview):
    yearly = load("yearly_trend.csv")
    total = yearly["sale_dollars"].sum()
    assert total == pytest.approx(overview["total_sale_dollars"], rel=0.001)
    rows = yearly["invoice_lines"].sum()
    assert rows == pytest.approx(overview["total_rows"], rel=0.001)


def test_yearly_columns_and_no_negatives():
    yearly = load("yearly_trend.csv")
    for col in ["year", "sale_dollars", "bottles_sold", "liters_sold",
                "invoice_lines", "yoy_growth_pct"]:
        assert col in yearly.columns
    assert (yearly["sale_dollars"] > 0).all()
    assert (yearly["bottles_sold"] > 0).all()
    assert yearly["year"].is_monotonic_increasing
    assert yearly["year"].min() == 2012


def test_monthly_coverage():
    monthly = load("monthly_trend.csv")
    # 2012-01 through the last extract month, well over a decade of months.
    assert len(monthly) >= 150
    assert (monthly["sale_dollars"] > 0).all()


def test_category_shares_sum_to_100():
    cat = load("category_totals.csv")
    assert cat["share_pct"].sum() == pytest.approx(100.0, abs=0.5)
    total = cat["sale_dollars"].sum()
    overview = load("overview.csv").iloc[0]
    # A small share of rows has no category in the source; allow 2 percent.
    assert total == pytest.approx(overview["total_sale_dollars"], rel=0.02)
    assert (cat["sale_dollars"] > 0).all()


def test_category_by_year_shares():
    yc = load("category_by_year.csv")
    per_year = yc.groupby("year")["share_pct_in_year"].sum()
    assert per_year.between(98.5, 101.5).all()


def test_county_totals_reconcile():
    counties = load("county_totals.csv")
    overview = load("overview.csv").iloc[0]
    assert counties["sale_dollars"].sum() == pytest.approx(
        overview["total_sale_dollars"], rel=0.02)
    assert counties["share_pct"].sum() == pytest.approx(100.0, abs=1.0)


def test_vendor_totals_reconcile():
    vendors = load("vendor_totals.csv")
    overview = load("overview.csv").iloc[0]
    assert vendors["sale_dollars"].sum() == pytest.approx(
        overview["total_sale_dollars"], rel=0.02)
    assert vendors["share_pct"].sum() == pytest.approx(100.0, abs=1.0)
    assert vendors["sale_dollars"].is_monotonic_decreasing


def test_store_totals_sorted_and_positive():
    stores = load("store_totals.csv")
    assert stores["sale_dollars"].is_monotonic_decreasing
    assert (stores["sale_dollars"] > 0).all()
    assert stores["cumulative_share_pct"].iloc[-1] == pytest.approx(100.0, abs=0.5)
    top = load("top_stores.csv")
    assert len(top) == 25


def test_seasonality_profile():
    seas = load("seasonality.csv")
    assert len(seas) == 12
    assert seas["seasonality_index"].mean() == pytest.approx(100.0, abs=1.0)
    assert set(seas["month"]) == set(range(1, 13))


def test_segment_shares():
    seg = load("segment_totals.csv")
    assert seg["share_pct"].sum() == pytest.approx(100.0, abs=0.5)
    assert set(seg["segment"]) == {
        "Value (<15)", "Core (15-25)", "Premium (25-40)", "Super premium (40+)"}


def test_price_by_category_sane():
    price = load("price_by_category.csv")
    assert (price["weighted_price_per_liter"] > 0).all()
    assert (price["weighted_price_per_liter"] < 200).all()
    assert (price["median_line_price_per_liter_approx"] > 0).all()


def test_data_quality_bounds(overview):
    quality = load("data_quality.csv").set_index("check")["rows"]
    # Negative lines exist in the source (returns and corrections) but must
    # stay a small fraction of all rows.
    assert quality["negative_sales_rows"] < overview["total_rows"] * 0.02
    assert quality["null_category_rows"] < overview["total_rows"] * 0.02


def test_anomaly_outputs():
    stores = load("anomalies_stores.csv")
    items = load("anomalies_items.csv")
    assert len(stores) > 0 and len(items) > 0
    assert (stores["z_score"].abs() >= 3).all()
    assert (items["z_score"].abs() >= 3).all()
