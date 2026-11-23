"""
fetch_and_aggregate.py

Downloads the official Iowa Liquor Sales yearly exports from the Iowa Data
Hub (data.iowa.gov, backend idh-be.iowa.gov) and computes every aggregate
used by this project, streaming the CSV parts in chunks so memory stays low.

Why this exists: the analysis SQL in ../sql is written for Google BigQuery
(public dataset bigquery-public-data.iowa_liquor_sales). The published result
tables in ../data/results were computed from the State of Iowa's own open
data exports, which are the same official dataset the BigQuery public table
is built from. Column names in the hub export differ slightly from BigQuery
(for example ordered_on instead of date, sales_dollars in both).

Data quality note: the hub export generator sometimes writes overlapping
part files inside a yearly zip, repeating identical rows (verified for
parts of 2020, 2021, 2022 and 2025). The aggregation therefore removes
exact full row duplicates (same invoice id and every other column) before
computing anything, which brings the row count in line with the official
combined dataset (35,287,731 rows as published by the hub catalog).

Iowa Data Hub dataset ids for the yearly files:
  2012: 1249, 2013: 1250, 2014: 1251, 2015: 1252, 2016: 1253, 2017: 1254,
  2018: 1255, 2019: 1256, 2020: 1257, 2021: 1258, 2022: 1259, 2023: 1260,
  2024: 1261, 2025: 1262, 2026: 1263

Usage:
  python3 fetch_and_aggregate.py download   # fetch any missing yearly zips
  python3 fetch_and_aggregate.py aggregate  # compute data/results/*.csv
"""

import io
import os
import sys
import time
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "data", "raw_download")
RESULTS_DIR = os.path.join(PROJECT_DIR, "data", "results")

YEAR_DATASET_IDS = {
    2012: 1249, 2013: 1250, 2014: 1251, 2015: 1252, 2016: 1253,
    2017: 1254, 2018: 1255, 2019: 1256, 2020: 1257, 2021: 1258,
    2022: 1259, 2023: 1260, 2024: 1261, 2025: 1262, 2026: 1263,
}

USECOLS = [
    "invoice_id", "ordered_on", "store_no", "store_name", "store_city",
    "county_name", "category_name", "vendor_number", "vendor_name",
    "item_no", "im_desc", "sales_bottles", "sales_dollars", "sales_liters",
]

PRICE_BIN_WIDTH = 0.5
PRICE_BIN_MAX = 300.0


def download():
    os.makedirs(RAW_DIR, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    for year, ds_id in YEAR_DATASET_IDS.items():
        path = os.path.join(RAW_DIR, f"sales_{year}.zip")
        if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
            print(f"{year}: already present, skipped")
            continue
        url = f"https://idh-be.iowa.gov/api/v1/datasets/{ds_id}/rows.csv"
        print(f"{year}: downloading dataset {ds_id} ...", flush=True)
        with requests.get(url, headers=headers, stream=True, timeout=900) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        print(f"{year}: saved {os.path.getsize(path):,} bytes")
        time.sleep(3)


def _add(store, key, dollars, bottles, liters, lines=1):
    cell = store.get(key)
    if cell is None:
        store[key] = [dollars, bottles, liters, lines]
    else:
        cell[0] += dollars
        cell[1] += bottles
        cell[2] += liters
        cell[3] += lines


def segment_of(price_per_liter):
    if price_per_liter < 15:
        return "Value (<15)"
    if price_per_liter < 25:
        return "Core (15-25)"
    if price_per_liter < 40:
        return "Premium (25-40)"
    return "Super premium (40+)"


def aggregate():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    totals = {"rows": 0, "dollars": 0.0, "bottles": 0.0, "liters": 0.0,
              "min_date": "9999", "max_date": ""}
    quality = defaultdict(int)
    by_year = {}
    by_month = {}          # (year, month)
    by_category = {}
    by_year_category = {}
    by_store = {}
    by_county = {}
    by_vendor = {}
    by_year_vendor = {}
    by_segment = {}
    by_year_segment = {}
    by_category_segment = {}
    store_month = {}
    item_month = {}
    store_info = {}
    item_info = {}
    vendor_names = {}
    price_hist = defaultdict(lambda: np.zeros(int(PRICE_BIN_MAX / PRICE_BIN_WIDTH) + 1))

    for year in sorted(YEAR_DATASET_IDS):
        path = os.path.join(RAW_DIR, f"sales_{year}.zip")
        if not os.path.exists(path):
            print(f"{year}: MISSING zip, skipped")
            continue
        print(f"{year}: aggregating ...", flush=True)
        # The hub export generator sometimes writes overlapping part files,
        # so identical rows (same invoice id and every other column) can
        # appear twice inside one yearly zip. Pass 1 hashes every full row
        # and builds a keep-first-occurrence mask; pass 2 aggregates only
        # the kept rows. See README, Data quality notes.
        keep_mask = _year_keep_mask(path)
        quality["duplicate_full_rows_removed"] += int((~keep_mask).sum())
        offset = 0
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if not name.endswith(".csv"):
                    continue
                with zf.open(name) as fh:
                    reader = pd.read_csv(
                        fh, usecols=USECOLS, dtype=str,
                        chunksize=400_000, low_memory=False,
                    )
                    for chunk in reader:
                        mask = keep_mask[offset:offset + len(chunk)]
                        offset += len(chunk)
                        chunk = chunk[mask]
                        if len(chunk):
                            _process_chunk(
                                chunk, totals, quality, by_year,
                                by_month, by_category, by_year_category, by_store,
                                by_county, by_vendor, by_year_vendor, by_segment,
                                by_year_segment, by_category_segment, store_month,
                                item_month, store_info, item_info, vendor_names,
                                price_hist,
                            )
        print(f"{year}: done, cumulative rows = {totals['rows']:,}")

    _write_results(
        totals, quality, by_year, by_month, by_category, by_year_category,
        by_store, by_county, by_vendor, by_year_vendor, by_segment,
        by_year_segment, by_category_segment, store_month, item_month,
        store_info, item_info, vendor_names, price_hist,
    )
    print("All result CSVs written to", RESULTS_DIR)
    print("TOTALS:", {k: totals[k] for k in ("rows", "dollars", "bottles", "liters")})
    print("DATE RANGE:", totals["min_date"], "to", totals["max_date"])


def _year_keep_mask(path):
    """Boolean mask over all rows of one yearly zip: True for the first
    occurrence of each fully identical row, False for exact repeats."""
    hashes = []
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as fh:
                reader = pd.read_csv(fh, dtype=str, chunksize=400_000,
                                     low_memory=False)
                for chunk in reader:
                    hashes.append(
                        pd.util.hash_pandas_object(chunk, index=False).values)
    all_hashes = np.concatenate(hashes) if hashes else np.array([], dtype="uint64")
    _, first_idx = np.unique(all_hashes, return_index=True)
    keep = np.zeros(len(all_hashes), dtype=bool)
    keep[first_idx] = True
    return keep


def _process_chunk(chunk, totals, quality, by_year, by_month,
                   by_category, by_year_category, by_store, by_county,
                   by_vendor, by_year_vendor, by_segment, by_year_segment,
                   by_category_segment, store_month, item_month, store_info,
                   item_info, vendor_names, price_hist):
    dates = chunk["ordered_on"].astype(str)
    yrs = dates.str.slice(0, 4)
    mos = dates.str.slice(5, 7)
    valid_year = yrs.str.fullmatch(r"\d{4}")
    chunk = chunk[valid_year]
    dates = dates[valid_year]
    yrs = yrs[valid_year].astype(int)
    mos = mos[valid_year].astype(int)

    dollars = pd.to_numeric(chunk["sales_dollars"], errors="coerce").fillna(0.0)
    bottles = pd.to_numeric(chunk["sales_bottles"], errors="coerce").fillna(0.0)
    liters = pd.to_numeric(chunk["sales_liters"], errors="coerce").fillna(0.0)

    totals["rows"] += len(chunk)
    totals["dollars"] += float(dollars.sum())
    totals["bottles"] += float(bottles.sum())
    totals["liters"] += float(liters.sum())
    dmin, dmax = dates.min(), dates.max()
    if dmin < totals["min_date"]:
        totals["min_date"] = dmin
    if dmax > totals["max_date"]:
        totals["max_date"] = dmax

    quality["null_category_rows"] += int(chunk["category_name"].isna().sum())
    quality["null_vendor_rows"] += int(chunk["vendor_name"].isna().sum())
    quality["null_county_rows"] += int(chunk["county_name"].isna().sum())
    quality["negative_sales_rows"] += int((dollars < 0).sum())
    quality["zero_sales_rows"] += int((dollars == 0).sum())
    quality["nonpositive_bottle_rows"] += int((bottles <= 0).sum())
    quality["negative_volume_rows"] += int((liters < 0).sum())

    df = pd.DataFrame({
        "year": yrs.values, "month": mos.values,
        "category": chunk["category_name"].fillna("").values,
        "store": chunk["store_no"].fillna("").values,
        "county": chunk["county_name"].fillna("").values,
        "vendor": chunk["vendor_number"].fillna("").values,
        "item": chunk["item_no"].fillna("").values,
        "dollars": dollars.values, "bottles": bottles.values,
        "liters": liters.values,
    })

    def accumulate(group_cols, store):
        g = df.groupby(group_cols, sort=False)[["dollars", "bottles", "liters"]].sum()
        counts = df.groupby(group_cols, sort=False).size()
        for key, row in g.iterrows():
            k = key if isinstance(key, tuple) else (key,)
            _add(store, k, float(row["dollars"]), float(row["bottles"]),
                 float(row["liters"]), int(counts.loc[key]))

    accumulate(["year"], by_year)
    accumulate(["year", "month"], by_month)
    accumulate(["category"], by_category)
    accumulate(["year", "category"], by_year_category)
    accumulate(["store"], by_store)
    accumulate(["county"], by_county)
    accumulate(["vendor"], by_vendor)
    accumulate(["year", "vendor"], by_year_vendor)
    accumulate(["store", "year", "month"], store_month)
    accumulate(["item", "year", "month"], item_month)

    # Price segmentation on invoice lines with positive volume and sales.
    pos = df[(df["liters"] > 0) & (df["dollars"] > 0)]
    if len(pos):
        ppl = pos["dollars"] / pos["liters"]
        segs = pd.cut(
            ppl, bins=[-np.inf, 15, 25, 40, np.inf],
            labels=["Value (<15)", "Core (15-25)", "Premium (25-40)",
                    "Super premium (40+)"],
        )
        seg_df = pd.DataFrame({
            "year": pos["year"].values, "category": pos["category"].values,
            "segment": segs.astype(str).values,
            "dollars": pos["dollars"].values, "liters": pos["liters"].values,
        })
        for cols, store in ((["segment"], by_segment),
                            (["year", "segment"], by_year_segment),
                            (["category", "segment"], by_category_segment)):
            g = seg_df.groupby(cols, sort=False)[["dollars", "liters"]].sum()
            counts = seg_df.groupby(cols, sort=False).size()
            for key, row in g.iterrows():
                k = key if isinstance(key, tuple) else (key,)
                cell = store.get(k)
                if cell is None:
                    store[k] = [float(row["dollars"]), float(row["liters"]),
                                int(counts.loc[key])]
                else:
                    cell[0] += float(row["dollars"])
                    cell[1] += float(row["liters"])
                    cell[2] += int(counts.loc[key])
        # Approximate price per liter distribution per category (histogram).
        bins = np.minimum((ppl / PRICE_BIN_WIDTH).astype(int),
                          int(PRICE_BIN_MAX / PRICE_BIN_WIDTH))
        hist_df = pd.DataFrame({"category": pos["category"].values,
                                "bin": bins.values})
        for cat, grp in hist_df.groupby("category"):
            counts = grp["bin"].value_counts()
            price_hist[cat][counts.index.values.astype(int)] += counts.values

    # Reference info: first seen names win.
    for no, nm, city, county in zip(chunk["store_no"].fillna(""),
                                    chunk["store_name"].fillna(""),
                                    chunk["store_city"].fillna(""),
                                    chunk["county_name"].fillna("")):
        if no and no not in store_info:
            store_info[no] = (nm, city, county)
    for no, desc in zip(chunk["item_no"].fillna(""), chunk["im_desc"].fillna("")):
        if no and no not in item_info:
            item_info[no] = desc
    for no, nm in zip(chunk["vendor_number"].fillna(""),
                      chunk["vendor_name"].fillna("")):
        if no and no not in vendor_names:
            vendor_names[no] = nm


def _frame(store, cols):
    rows = []
    for key, vals in store.items():
        rows.append(tuple(key) + tuple(vals))
    return pd.DataFrame(rows, columns=cols)


def _write_results(totals, quality, by_year, by_month, by_category,
                   by_year_category, by_store, by_county, by_vendor,
                   by_year_vendor, by_segment, by_year_segment,
                   by_category_segment, store_month, item_month, store_info,
                   item_info, vendor_names, price_hist):
    w = lambda name, df: df.to_csv(os.path.join(RESULTS_DIR, name), index=False)

    overview = pd.DataFrame([{
        "total_rows": totals["rows"],
        "first_date": totals["min_date"][:10],
        "last_date": totals["max_date"][:10],
        "distinct_stores": len(by_store),
        "distinct_items": len({k[0] for k in item_month}),
        "distinct_vendors": len(by_vendor),
        "distinct_counties": len([k for k in by_county if k[0]]),
        "total_sale_dollars": round(totals["dollars"], 2),
        "total_bottles_sold": int(totals["bottles"]),
        "total_liters_sold": round(totals["liters"], 2),
    }])
    w("overview.csv", overview)

    q = pd.DataFrame([{"check": k, "rows": int(v)} for k, v in sorted(quality.items())])
    w("data_quality.csv", q)

    yearly = _frame(by_year, ["year", "sale_dollars", "bottles_sold",
                              "liters_sold", "invoice_lines"])
    yearly = yearly.sort_values("year")
    yearly["yoy_growth_pct"] = (
        yearly["sale_dollars"].pct_change() * 100).round(2)
    w("yearly_trend.csv", yearly)

    monthly = _frame(by_month, ["year", "month", "sale_dollars", "bottles_sold",
                                "liters_sold", "invoice_lines"])
    monthly = monthly.sort_values(["year", "month"])
    monthly["month_start"] = pd.to_datetime(
        monthly["year"].astype(str) + "-" + monthly["month"].astype(str).str.zfill(2) + "-01")
    monthly["sale_dollars_3mo_avg"] = (
        monthly["sale_dollars"].rolling(3, center=True, min_periods=1).mean().round(2))
    w("monthly_trend.csv", monthly)

    # Seasonality over complete years only (all 12 months present, and the
    # year is not the first or last partial year of the extract).
    counts = monthly.groupby("year")["month"].nunique()
    complete = counts[counts == 12].index.tolist()
    if len(complete) > 2:
        complete = complete[1:-1] if monthly["year"].max() in complete and \
            monthly[monthly["year"] == monthly["year"].max()]["month"].max() < 12 else complete
    seas = monthly[monthly["year"].isin(complete)].groupby("month").agg(
        avg_sale_dollars=("sale_dollars", "mean"),
        years_observed=("year", "nunique")).reset_index()
    seas["seasonality_index"] = (
        100 * seas["avg_sale_dollars"] / seas["avg_sale_dollars"].mean()).round(1)
    seas["complete_years_used"] = ",".join(str(y) for y in complete)
    w("seasonality.csv", seas)

    cat = _frame(by_category, ["category_name", "sale_dollars", "bottles_sold",
                               "liters_sold", "invoice_lines"])
    cat = cat[cat["category_name"] != ""]
    cat["share_pct"] = (100 * cat["sale_dollars"] / cat["sale_dollars"].sum()).round(2)
    cat = cat.sort_values("sale_dollars", ascending=False)
    w("category_totals.csv", cat)

    yc = _frame(by_year_category, ["year", "category_name", "sale_dollars",
                                   "bottles_sold", "liters_sold", "invoice_lines"])
    yc = yc[yc["category_name"] != ""]
    yc["share_pct_in_year"] = (
        100 * yc["sale_dollars"]
        / yc.groupby("year")["sale_dollars"].transform("sum")).round(2)
    w("category_by_year.csv", yc.sort_values(["year", "sale_dollars"],
                                             ascending=[True, False]))

    stores = _frame(by_store, ["store_number", "sale_dollars", "bottles_sold",
                               "liters_sold", "invoice_lines"])
    stores["store_name"] = stores["store_number"].map(
        lambda n: store_info.get(n, ("", "", ""))[0])
    stores["city"] = stores["store_number"].map(
        lambda n: store_info.get(n, ("", "", ""))[1])
    stores["county"] = stores["store_number"].map(
        lambda n: store_info.get(n, ("", "", ""))[2])
    stores = stores.sort_values("sale_dollars", ascending=False)
    stores["share_pct"] = (100 * stores["sale_dollars"]
                           / stores["sale_dollars"].sum()).round(4)
    stores["cumulative_share_pct"] = stores["share_pct"].cumsum().round(4)
    w("store_totals.csv", stores)
    w("top_stores.csv", stores.head(25))

    counties = _frame(by_county, ["county", "sale_dollars", "bottles_sold",
                                  "liters_sold", "invoice_lines"])
    counties = counties[counties["county"] != ""]
    counties["share_pct"] = (100 * counties["sale_dollars"]
                             / counties["sale_dollars"].sum()).round(2)
    store_counts = stores.groupby("county")["store_number"].nunique()
    counties["stores"] = counties["county"].map(store_counts).fillna(0).astype(int)
    w("county_totals.csv", counties.sort_values("sale_dollars", ascending=False))

    vendors = _frame(by_vendor, ["vendor_number", "sale_dollars", "bottles_sold",
                                 "liters_sold", "invoice_lines"])
    vendors["vendor_name"] = vendors["vendor_number"].map(vendor_names)
    vendors["share_pct"] = (100 * vendors["sale_dollars"]
                            / vendors["sale_dollars"].sum()).round(2)
    vendors = vendors.sort_values("sale_dollars", ascending=False)
    vendors["cumulative_share_pct"] = vendors["share_pct"].cumsum().round(2)
    w("vendor_totals.csv", vendors)
    w("top_vendors.csv", vendors.head(20))

    yv = _frame(by_year_vendor, ["year", "vendor_number", "sale_dollars",
                                 "bottles_sold", "liters_sold", "invoice_lines"])
    yv["vendor_name"] = yv["vendor_number"].map(vendor_names)
    yv["share_pct_in_year"] = (
        100 * yv["sale_dollars"]
        / yv.groupby("year")["sale_dollars"].transform("sum")).round(2)
    w("vendor_by_year.csv", yv.sort_values(["year", "sale_dollars"],
                                          ascending=[True, False]))

    seg = _frame(by_segment, ["segment", "sale_dollars", "liters_sold",
                              "invoice_lines"])
    seg["share_pct"] = (100 * seg["sale_dollars"] / seg["sale_dollars"].sum()).round(2)
    w("segment_totals.csv", seg)

    yseg = _frame(by_year_segment, ["year", "segment", "sale_dollars",
                                    "liters_sold", "invoice_lines"])
    yseg["share_pct_in_year"] = (
        100 * yseg["sale_dollars"]
        / yseg.groupby("year")["sale_dollars"].transform("sum")).round(2)
    w("segment_by_year.csv", yseg.sort_values(["year", "segment"]))

    cseg = _frame(by_category_segment, ["category_name", "segment", "sale_dollars",
                                        "liters_sold", "invoice_lines"])
    cseg = cseg[cseg["category_name"] != ""]
    cseg["share_pct_in_category"] = (
        100 * cseg["sale_dollars"]
        / cseg.groupby("category_name")["sale_dollars"].transform("sum")).round(2)
    w("segment_by_category.csv", cseg)

    # Price per liter by category: weighted mean plus histogram based
    # approximate percentiles of the per line price per liter.
    price_rows = []
    for _, row in cat.iterrows():
        name = row["category_name"]
        hist = price_hist.get(name)
        total_lines = hist.sum() if hist is not None else 0
        med = p25 = p75 = np.nan
        if total_lines > 0:
            cdf = np.cumsum(hist) / total_lines
            centers = (np.arange(len(hist)) + 0.5) * PRICE_BIN_WIDTH
            med = float(centers[np.searchsorted(cdf, 0.50)])
            p25 = float(centers[np.searchsorted(cdf, 0.25)])
            p75 = float(centers[np.searchsorted(cdf, 0.75)])
        price_rows.append({
            "category_name": name,
            "invoice_lines": int(row["invoice_lines"]),
            "weighted_price_per_liter": round(row["sale_dollars"] / row["liters_sold"], 2),
            "median_line_price_per_liter_approx": med,
            "p25_line_price_per_liter_approx": p25,
            "p75_line_price_per_liter_approx": p75,
        })
    w("price_by_category.csv", pd.DataFrame(price_rows).sort_values(
        "weighted_price_per_liter", ascending=False))

    sm = _frame(store_month, ["store_number", "year", "month", "sale_dollars",
                              "bottles_sold", "liters_sold", "invoice_lines"])
    sm["store_name"] = sm["store_number"].map(
        lambda n: store_info.get(n, ("", "", ""))[0])
    sm["month_start"] = pd.to_datetime(
        sm["year"].astype(str) + "-" + sm["month"].astype(str).str.zfill(2) + "-01")
    w("store_monthly.csv", sm.sort_values(["store_number", "month_start"]))

    im = _frame(item_month, ["item_number", "year", "month", "sale_dollars",
                             "bottles_sold", "liters_sold", "invoice_lines"])
    im["item_description"] = im["item_number"].map(item_info)
    im["month_start"] = pd.to_datetime(
        im["year"].astype(str) + "-" + im["month"].astype(str).str.zfill(2) + "-01")
    w("item_monthly.csv", im.sort_values(["item_number", "month_start"]))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "aggregate"
    if mode == "download":
        download()
    else:
        aggregate()
