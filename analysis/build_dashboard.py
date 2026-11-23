"""
build_dashboard.py

Builds dashboard/index.html, a single self-contained interactive dashboard
(no external libraries, no network calls) from the aggregate CSVs in
data/results. Charts are inline SVG generated here; small JavaScript tab
buttons switch between views and table rows highlight on hover.
"""

import html
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
RESULTS = os.path.join(PROJECT_DIR, "data", "results")
OUT = os.path.join(PROJECT_DIR, "dashboard", "index.html")


def money(x):
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.1f}K"
    return f"${x:,.0f}"


def bar_svg(labels, values, color="#8c4a12", width=760, row_h=26, fmt=None):
    fmt = fmt or money
    max_v = max(values) if values else 1
    label_w = 210
    chart_w = width - label_w - 90
    height = row_h * len(labels) + 8
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = i * row_h + 4
        w = chart_w * (val / max_v) if max_v else 0
        parts.append(
            f'<text x="{label_w - 8}" y="{y + row_h / 2 + 4}" text-anchor="end" '
            f'font-size="12" fill="#333">{html.escape(str(lab))}</text>')
        parts.append(
            f'<rect x="{label_w}" y="{y + 3}" width="{w:.1f}" '
            f'height="{row_h - 8}" fill="{color}" rx="3">'
            f'<title>{html.escape(str(lab))}: {fmt(val)}</title></rect>')
        parts.append(
            f'<text x="{label_w + w + 6}" y="{y + row_h / 2 + 4}" '
            f'font-size="12" fill="#333">{fmt(val)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def line_svg(xs, ys, color="#8c4a12", width=760, height=260, fmt=None):
    fmt = fmt or money
    if not len(ys):
        return ""
    min_y, max_y = min(ys), max(ys)
    pad = (max_y - min_y) * 0.08 or 1
    min_y -= pad
    max_y += pad
    left, right, top, bottom = 64, 10, 12, 26
    iw, ih = width - left - right, height - top - bottom

    def px(i):
        return left + iw * i / max(len(xs) - 1, 1)

    def py(v):
        return top + ih * (1 - (v - min_y) / (max_y - min_y))

    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(ys))
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for frac in (0, 0.5, 1.0):
        v = min_y + (max_y - min_y) * frac
        y = py(v)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            f'stroke="#e2e2e2" stroke-width="1"/>')
        parts.append(
            f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#666">{fmt(v)}</text>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                 f'stroke-width="2"/>')
    step = max(len(xs) // 10, 1)
    for i in range(0, len(xs), step):
        parts.append(
            f'<text x="{px(i):.1f}" y="{height - 6}" text-anchor="middle" '
            f'font-size="11" fill="#666">{html.escape(str(xs[i]))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def table_html(df, cols, formatters=None, limit=None):
    formatters = formatters or {}
    if limit:
        df = df.head(limit)
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if c in formatters:
                v = formatters[c](v)
            cells.append(f"<td>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def main():
    ov = pd.read_csv(os.path.join(RESULTS, "overview.csv")).iloc[0]
    yearly = pd.read_csv(os.path.join(RESULTS, "yearly_trend.csv"))
    monthly = pd.read_csv(os.path.join(RESULTS, "monthly_trend.csv"))
    seas = pd.read_csv(os.path.join(RESULTS, "seasonality.csv"))
    cat = pd.read_csv(os.path.join(RESULTS, "category_totals.csv"))
    stores = pd.read_csv(os.path.join(RESULTS, "top_stores.csv"))
    counties = pd.read_csv(os.path.join(RESULTS, "county_totals.csv"))
    vendors = pd.read_csv(os.path.join(RESULTS, "top_vendors.csv"))
    price = pd.read_csv(os.path.join(RESULTS, "price_by_category.csv"))
    seg = pd.read_csv(os.path.join(RESULTS, "segment_totals.csv"))
    anom_s = pd.read_csv(os.path.join(RESULTS, "anomalies_stores.csv"))
    anom_i = pd.read_csv(os.path.join(RESULTS, "anomalies_items.csv"))

    kpis = [
        ("Total sales", money(ov["total_sale_dollars"])),
        ("Invoice lines", f"{int(ov['total_rows']):,}"),
        ("Period", f"{ov['first_date']} to {ov['last_date']}"),
        ("Stores", f"{int(ov['distinct_stores']):,}"),
        ("Products (items)", f"{int(ov['distinct_items']):,}"),
        ("Vendors", f"{int(ov['distinct_vendors']):,}"),
        ("Bottles sold", f"{int(ov['total_bottles_sold']):,}"),
        ("Liters sold", f"{ov['total_liters_sold']:,.0f}"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{html.escape(k)}</div>'
        f'<div class="kpi-value">{html.escape(v)}</div></div>'
        for k, v in kpis)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seas_chart = bar_svg(
        [month_names[m - 1] for m in seas["month"]],
        seas["seasonality_index"].tolist(), color="#2e6f8e",
        fmt=lambda v: f"{v:.0f}")
    monthly_chart = line_svg(
        monthly["month_start"].astype(str).str.slice(0, 7).tolist(),
        monthly["sale_dollars"].tolist())
    yearly_chart = bar_svg(
        yearly["year"].astype(str).tolist(),
        yearly["sale_dollars"].tolist())
    cat_chart = bar_svg(
        cat.head(10)["category_name"].tolist(),
        cat.head(10)["share_pct"].tolist(),
        fmt=lambda v: f"{v:.1f}%")
    seg_chart = bar_svg(
        seg["segment"].tolist(), seg["share_pct"].tolist(),
        color="#2e6f8e", fmt=lambda v: f"{v:.1f}%")
    price_chart = bar_svg(
        price.head(12)["category_name"].tolist(),
        price.head(12)["weighted_price_per_liter"].tolist(),
        fmt=lambda v: f"${v:.2f}/L")

    stores_table = table_html(
        stores, ["store_name", "city", "county", "sale_dollars", "share_pct"],
        {"sale_dollars": money, "share_pct": lambda v: f"{v:.2f}%"}, limit=15)
    counties_table = table_html(
        counties, ["county", "sale_dollars", "share_pct", "stores"],
        {"sale_dollars": money, "share_pct": lambda v: f"{v:.2f}%"}, limit=15)
    vendors_table = table_html(
        vendors, ["vendor_name", "sale_dollars", "share_pct",
                  "cumulative_share_pct"],
        {"sale_dollars": money, "share_pct": lambda v: f"{v:.2f}%",
         "cumulative_share_pct": lambda v: f"{v:.2f}%"}, limit=15)
    anom_s_table = table_html(
        anom_s, ["store_name", "month_start", "sale_dollars", "z_score"],
        {"sale_dollars": money, "z_score": lambda v: f"{v:.1f}",
         "month_start": lambda v: str(v)[:7]}, limit=15)
    anom_i_table = table_html(
        anom_i, ["item_description", "month_start", "sale_dollars", "z_score"],
        {"sale_dollars": money, "z_score": lambda v: f"{v:.1f}",
         "month_start": lambda v: str(v)[:7]}, limit=15)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Iowa Liquor Sales Analytics Dashboard</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         margin: 0; background: #f6f3ef; color: #26221e; }}
  header {{ background: #3d2410; color: #fdf9f3; padding: 22px 28px; }}
  header h1 {{ margin: 0 0 4px; font-size: 24px; }}
  header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  main {{ max-width: 1060px; margin: 0 auto; padding: 20px 16px 40px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 10px; margin-bottom: 18px; }}
  .kpi {{ background: #fff; border: 1px solid #e4ddd2; border-radius: 10px;
         padding: 12px 14px; }}
  .kpi-label {{ font-size: 12px; color: #7a6a58; text-transform: uppercase;
               letter-spacing: 0.04em; }}
  .kpi-value {{ font-size: 19px; font-weight: 700; margin-top: 3px; }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
  .tabs button {{ border: 1px solid #cdbfa9;
    background: #fff; color: #3d2410; padding: 8px 14px; border-radius: 999px;
    cursor: pointer; font-size: 14px; }}
  .tabs button.active {{ background: #8c4a12; color: #fff; border-color: #8c4a12; }}
  .panel {{ display: none; background: #fff; border: 1px solid #e4ddd2;
           border-radius: 12px; padding: 18px; }}
  .panel.active {{ display: block; }}
  .panel h2 {{ margin: 2px 0 4px; font-size: 18px; }}
  .panel p.note {{ color: #6b5d4c; font-size: 13px; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
  th, td {{ text-align: left; padding: 7px 9px; border-bottom: 1px solid #eee5d8; }}
  th {{ background: #faf6f0; }}
  tbody tr:hover {{ background: #fdf3e3; }}
  footer {{ color: #7a6a58; font-size: 12.5px; text-align: center; padding: 14px; }}
</style>
</head>
<body>
<header>
  <h1>Iowa Liquor Sales Analytics</h1>
  <p>BigQuery public dataset bigquery-public-data.iowa_liquor_sales, results computed from the official Iowa open data exports of the same dataset.</p>
</header>
<main>
  <section class="kpis">{kpi_html}</section>
  <nav class="tabs">
    <button data-tab="trend" class="active">Trend</button>
    <button data-tab="season">Seasonality</button>
    <button data-tab="category">Categories</button>
    <button data-tab="geo">Stores and counties</button>
    <button data-tab="vendor">Vendors</button>
    <button data-tab="price">Prices and segments</button>
    <button data-tab="anomaly">Anomalies</button>
  </nav>

  <section class="panel active" id="trend">
    <h2>Sales trend</h2>
    <p class="note">Total wholesale liquor sales by Iowa Class E licensees per month and per year, in USD.</p>
    {monthly_chart}
    {yearly_chart}
  </section>

  <section class="panel" id="season">
    <h2>Seasonality index by calendar month</h2>
    <p class="note">100 is an exactly average month. Computed over complete calendar years only.</p>
    {seas_chart}
  </section>

  <section class="panel" id="category">
    <h2>Top categories by share of sales</h2>
    <p class="note">Share of all time sales in percent.</p>
    {cat_chart}
  </section>

  <section class="panel" id="geo">
    <h2>Top stores</h2>
    {stores_table}
    <h2 style="margin-top:22px">Top counties</h2>
    {counties_table}
  </section>

  <section class="panel" id="vendor">
    <h2>Top vendors</h2>
    <p class="note">Vendors supply the State of Iowa; stores buy from the state. Cumulative share shows supply side concentration.</p>
    {vendors_table}
  </section>

  <section class="panel" id="price">
    <h2>Price per liter by category</h2>
    <p class="note">Weighted mean price per liter (total dollars divided by total liters).</p>
    {price_chart}
    <h2 style="margin-top:22px">Sales share by price segment</h2>
    {seg_chart}
  </section>

  <section class="panel" id="anomaly">
    <h2>Most anomalous store months</h2>
    <p class="note">Z-score of a month against the store's own monthly history. Absolute z of 3 or more is flagged.</p>
    {anom_s_table}
    <h2 style="margin-top:22px">Most anomalous product months</h2>
    {anom_i_table}
  </section>
</main>
<footer>Data: State of Iowa, Iowa Liquor Sales (official open data). Analysis SQL for BigQuery is in the sql folder of the project repository.</footer>
<script>
  document.querySelectorAll(".tabs button").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      document.querySelectorAll(".tabs button").forEach(function (b) {{
        b.classList.remove("active");
      }});
      document.querySelectorAll(".panel").forEach(function (p) {{
        p.classList.remove("active");
      }});
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
    }});
  }});
</script>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("Dashboard written to", OUT)


if __name__ == "__main__":
    main()
