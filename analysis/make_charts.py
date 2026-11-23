"""
make_charts.py

Reads the aggregate CSVs in ../data/results and renders the charts used by
the README and the dashboard into ../charts as PNG files.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
RESULTS = os.path.join(PROJECT_DIR, "data", "results")
CHARTS = os.path.join(PROJECT_DIR, "charts")
os.makedirs(CHARTS, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.edgecolor": "#888888",
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.6,
})
ACCENT = "#8c4a12"
SECOND = "#2e6f8e"


def money(x):
    if x >= 1e9:
        return f"${x / 1e9:.2f}B"
    if x >= 1e6:
        return f"${x / 1e6:.0f}M"
    return f"${x:,.0f}"


def chart_yearly_trend():
    df = pd.read_csv(os.path.join(RESULTS, "yearly_trend.csv"))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(df["year"].astype(str), df["sale_dollars"] / 1e9,
           color=ACCENT, alpha=0.85)
    for x, y in zip(df["year"].astype(str), df["sale_dollars"] / 1e9):
        ax.text(x, y + 0.01, f"{y:.2f}", ha="center", fontsize=8)
    ax.set_title("Iowa liquor sales by year (billion USD)")
    ax.set_ylabel("Billion USD")
    ax.set_ylim(0, (df["sale_dollars"] / 1e9).max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "yearly_trend.png"))
    plt.close(fig)


def chart_monthly_trend():
    df = pd.read_csv(os.path.join(RESULTS, "monthly_trend.csv"),
                     parse_dates=["month_start"])
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(df["month_start"], df["sale_dollars"] / 1e6,
            color="#bbbbbb", linewidth=0.8, label="Monthly sales")
    ax.plot(df["month_start"], df["sale_dollars_3mo_avg"] / 1e6,
            color=ACCENT, linewidth=1.8, label="3 month average")
    ax.set_title("Monthly sales with 3 month moving average (million USD)")
    ax.set_ylabel("Million USD")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "monthly_trend.png"))
    plt.close(fig)


def chart_seasonality():
    df = pd.read_csv(os.path.join(RESULTS, "seasonality.csv"))
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    colors = [ACCENT if v >= 100 else SECOND for v in df["seasonality_index"]]
    ax.bar([names[m - 1] for m in df["month"]], df["seasonality_index"],
           color=colors)
    ax.axhline(100, color="#555555", linewidth=0.9, linestyle="--")
    ax.set_title("Seasonality index by calendar month (100 = average month)")
    ax.set_ylabel("Index")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "seasonality.png"))
    plt.close(fig)


def chart_category_share():
    df = pd.read_csv(os.path.join(RESULTS, "category_totals.csv")).head(10)
    df = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.barh(df["category_name"], df["share_pct"], color=ACCENT, alpha=0.9)
    for y, v in zip(df["category_name"], df["share_pct"]):
        ax.text(v + 0.15, y, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_title("Top 10 categories by share of all time sales")
    ax.set_xlabel("Share of total sales (%)")
    ax.set_xlim(0, df["share_pct"].max() * 1.18)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "category_share.png"))
    plt.close(fig)


def chart_category_share_shift():
    yc = pd.read_csv(os.path.join(RESULTS, "category_by_year.csv"))
    top = (pd.read_csv(os.path.join(RESULTS, "category_totals.csv"))
           .head(6)["category_name"].tolist())
    pivot = (yc[yc["category_name"].isin(top)]
             .pivot(index="year", columns="category_name",
                    values="share_pct_in_year").fillna(0))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    pivot.plot(ax=ax, linewidth=1.8, marker="o", markersize=3)
    ax.set_title("Share of yearly sales, top 6 categories (%)")
    ax.set_ylabel("Share (%)")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "category_share_by_year.png"))
    plt.close(fig)


def chart_concentration():
    df = pd.read_csv(os.path.join(RESULTS, "store_totals.csv"))
    n = len(df)
    x = [0] + [100 * (i + 1) / n for i in range(n)]
    y = [0] + df["cumulative_share_pct"].tolist()
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.plot(x, y, color=ACCENT, linewidth=2)
    ax.plot([0, 100], [0, 100], color="#999999", linestyle="--",
            linewidth=1, label="Perfect equality")
    ax.fill_between(x, y, alpha=0.12, color=ACCENT)
    ax.set_title("Store concentration curve (Lorenz curve)")
    ax.set_xlabel("Cumulative % of stores (smallest to largest)")
    ax.set_ylabel("Cumulative % of sales")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "store_concentration.png"))
    plt.close(fig)


def chart_top_counties():
    df = pd.read_csv(os.path.join(RESULTS, "county_totals.csv")).head(10)
    df = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.barh(df["county"], df["sale_dollars"] / 1e9, color=SECOND)
    for y, v in zip(df["county"], df["sale_dollars"] / 1e9):
        ax.text(v + 0.02, y, f"${v:.2f}B", va="center", fontsize=9)
    ax.set_title("Top 10 counties by all time sales (billion USD)")
    ax.set_xlabel("Billion USD")
    ax.set_xlim(0, (df["sale_dollars"] / 1e9).max() * 1.2)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "top_counties.png"))
    plt.close(fig)


def chart_price_by_category():
    df = pd.read_csv(os.path.join(RESULTS, "price_by_category.csv"))
    df = df[df["invoice_lines"] >= 1000].head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(df["category_name"], df["weighted_price_per_liter"], color=ACCENT)
    import numpy as np
    lower = np.maximum(
        df["weighted_price_per_liter"] - df["p25_line_price_per_liter_approx"], 0)
    upper = np.maximum(
        df["p75_line_price_per_liter_approx"] - df["weighted_price_per_liter"], 0)
    ax.errorbar(
        df["weighted_price_per_liter"], df["category_name"],
        xerr=[lower, upper],
        fmt="none", ecolor="#444444", elinewidth=1, capsize=3,
    )
    ax.set_title("Price per liter by category (USD, weighted mean; whiskers = approx. p25 to p75 of line prices)")
    ax.set_xlabel("USD per liter")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "price_by_category.png"))
    plt.close(fig)


def chart_segments():
    df = pd.read_csv(os.path.join(RESULTS, "segment_totals.csv"))
    order = ["Value (<15)", "Core (15-25)", "Premium (25-40)",
             "Super premium (40+)"]
    df["segment"] = pd.Categorical(df["segment"], categories=order, ordered=True)
    df = df.sort_values("segment")
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(df["segment"], df["share_pct"],
           color=[SECOND, ACCENT, "#c07a2a", "#5b3410"])
    for x, v in zip(df["segment"], df["share_pct"]):
        ax.text(x, v + 0.6, f"{v:.1f}%", ha="center", fontsize=10)
    ax.set_title("Sales share by price per liter segment (all years)")
    ax.set_ylabel("Share of sales (%)")
    ax.set_ylim(0, df["share_pct"].max() * 1.15)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "segment_share.png"))
    plt.close(fig)


def chart_vendors():
    df = pd.read_csv(os.path.join(RESULTS, "top_vendors.csv")).head(10)
    df = df.iloc[::-1]
    labels = [str(v)[:34] for v in df["vendor_name"]]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.barh(labels, df["share_pct"], color=SECOND)
    for y, v in zip(labels, df["share_pct"]):
        ax.text(v + 0.15, y, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_title("Top 10 vendors by share of all time sales")
    ax.set_xlabel("Share of total sales (%)")
    ax.set_xlim(0, df["share_pct"].max() * 1.2)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, "top_vendors.png"))
    plt.close(fig)


if __name__ == "__main__":
    chart_yearly_trend()
    chart_monthly_trend()
    chart_seasonality()
    chart_category_share()
    chart_category_share_shift()
    chart_concentration()
    chart_top_counties()
    chart_price_by_category()
    chart_segments()
    chart_vendors()
    print("Charts written to", CHARTS)
