"""
anomaly_detection.py

Simple z-score anomaly detection on the monthly series exported by
fetch_and_aggregate.py. For every store and every product item with at
least 24 months of history, each month is scored against that series' own
mean and population standard deviation. Months with |z| >= 3 are written
to data/results/anomalies_stores.csv and anomalies_items.csv, and the
single most extreme store and item series are plotted with their flagged
months into charts/.

The matching BigQuery version of this logic lives in
sql/07_anomaly_detection_inputs.sql.
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

MIN_MONTHS = 24
Z_THRESHOLD = 3.0


def score_series(df, id_col, label_col):
    out = []
    for key, grp in df.groupby(id_col):
        if len(grp) < MIN_MONTHS:
            continue
        mean = grp["sale_dollars"].mean()
        std = grp["sale_dollars"].std(ddof=0)
        if std == 0 or pd.isna(std):
            continue
        z = (grp["sale_dollars"] - mean) / std
        flagged = grp.assign(z_score=z.round(2))
        flagged = flagged[flagged["z_score"].abs() >= Z_THRESHOLD]
        for _, row in flagged.iterrows():
            out.append({
                id_col: key,
                label_col: row[label_col],
                "month_start": row["month_start"],
                "sale_dollars": round(float(row["sale_dollars"]), 2),
                "series_mean_monthly": round(float(mean), 2),
                "z_score": float(row["z_score"]),
            })
    result = pd.DataFrame(out)
    if len(result):
        result = result.reindex(
            result["z_score"].abs().sort_values(ascending=False).index)
    return result


def plot_worst(df, anomalies, id_col, label_col, filename, title):
    if not len(anomalies):
        print("No anomalies to plot for", filename)
        return
    worst_id = anomalies.iloc[0][id_col]
    series = df[df[id_col] == worst_id].sort_values("month_start")
    flags = anomalies[anomalies[id_col] == worst_id]
    label = str(series.iloc[0][label_col])[:60]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(series["month_start"], series["sale_dollars"] / 1e3,
            color="#8c4a12", linewidth=1.4)
    ax.scatter(pd.to_datetime(flags["month_start"]),
               flags["sale_dollars"] / 1e3,
               color="#c0272d", zorder=5, s=42, label="|z| >= 3")
    ax.set_title(f"{title}: {label}")
    ax.set_ylabel("Thousand USD per month")
    ax.legend(frameon=False)
    ax.grid(color="#dddddd", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS, filename))
    plt.close(fig)


def main():
    stores = pd.read_csv(os.path.join(RESULTS, "store_monthly.csv"),
                         parse_dates=["month_start"])
    items = pd.read_csv(os.path.join(RESULTS, "item_monthly.csv"),
                        parse_dates=["month_start"])

    store_anom = score_series(stores, "store_number", "store_name")
    item_anom = score_series(items, "item_number", "item_description")

    store_anom.to_csv(os.path.join(RESULTS, "anomalies_stores.csv"), index=False)
    item_anom.to_csv(os.path.join(RESULTS, "anomalies_items.csv"), index=False)

    plot_worst(stores, store_anom, "store_number", "store_name",
               "anomaly_store.png", "Most anomalous store month")
    plot_worst(items, item_anom, "item_number", "item_description",
               "anomaly_item.png", "Most anomalous product month")

    print(f"Store anomalies flagged: {len(store_anom)}")
    print(f"Item anomalies flagged: {len(item_anom)}")
    if len(store_anom):
        print("Worst store anomaly:")
        print(store_anom.head(3).to_string(index=False))
    if len(item_anom):
        print("Worst item anomaly:")
        print(item_anom.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
