"""Embed the cleaned star-schema data into the dashboard template.

Run from the repository root (after clean_data.py):  python scripts/build_dashboard.py

Reads  data/clean/*.csv and dashboard/dashboard_template.html
Writes dashboard/index.html  (one self-contained file, open it in any browser)
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
DASH = ROOT / "dashboard"

fact = pd.read_csv(
    CLEAN / "fact_sales.csv",
    dtype={"order_id": str, "customer_id": str, "product_id": str, "region_id": str},
)
customers = pd.read_csv(CLEAN / "dim_customer.csv", dtype=str)
products = pd.read_csv(CLEAN / "dim_product.csv", dtype=str)
regions = pd.read_csv(CLEAN / "dim_region.csv", dtype=str)

cats = sorted(products["category"].unique())
region_names = sorted(regions["region"].unique())
months = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]

month_idx = {m: i for i, m in enumerate(months)}
cust_idx = {c: i for i, c in enumerate(customers["customer_id"])}
prod_idx = {p: i for i, p in enumerate(products["product_id"])}
region_of = dict(zip(regions["region_id"], (region_names.index(r) for r in regions["region"])))

product_list = [
    {"id": r.product_id, "name": r.product_name, "cat": cats.index(r.category), "sub": r.sub_category}
    for r in products.itertuples()
]

# one compact row per order: [month, region, product, customer, sales, profit, quantity]
rows = [
    [
        -1 if pd.isna(r.order_date) else month_idx[r.order_date[:7]],
        region_of[r.region_id],
        prod_idx[r.product_id],
        cust_idx[r.customer_id],
        round(r.sales_amount, 2),
        round(r.profit, 2),
        int(r.quantity),
    ]
    for r in fact.itertuples()
]

data = {
    "months": months,
    "regions": region_names,
    "cats": cats,
    "products": product_list,
    "rows": rows,
    "meta": {
        "customers": len(customers),
        "products": len(products),
        "states": len(regions),
    },
}

template = (DASH / "dashboard_template.html").read_text(encoding="utf-8")
assert template.count("/*DATA*/null") == 1, "placeholder missing from template"
payload = json.dumps(data, separators=(",", ":"))
assert "</script" not in payload
(DASH / "index.html").write_text(template.replace("/*DATA*/null", payload), encoding="utf-8")
print("wrote dashboard/index.html with %d orders" % len(rows))
