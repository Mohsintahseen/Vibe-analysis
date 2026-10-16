"""Clean the four raw CSVs and build the star schema.

Run from the repository root:  python scripts/clean_data.py

Reads  data/raw/*.csv
Writes data/clean/{dim_customer,dim_product,dim_region,dim_date,fact_sales}.csv
       data/logs/{customer_duplicates_log,customer_signup_adjustments_log}.csv
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
LOGS = ROOT / "data" / "logs"
CLEAN.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

CATEGORY_NAMES = {
    "furniture": "Furniture",
    "electronics": "Electronics",
    "office supplies": "Office Supplies",
    "home & kitchen": "Home & Kitchen",
    "clothing": "Clothing",
}


def load_orders_deduped():
    """Raw orders with the 50 exact duplicate rows removed (as text)."""
    raw = pd.read_csv(RAW / "orders_raw.csv", dtype=str, keep_default_na=False)
    return raw, raw.drop_duplicates(keep="first").copy()


# ---------------------------------------------------------------- customers
def build_dim_customer(orders_dedup):
    raw = pd.read_csv(RAW / "customers_raw.csv", dtype=str, keep_default_na=False)

    dup_ids = raw[raw.duplicated("customer_id", keep=False)].copy()
    dup_ids["source_row"] = dup_ids.index + 2  # CSV line number incl. header
    dup_ids.sort_values(["customer_id", "source_row"]).to_csv(
        LOGS / "customer_duplicates_log.csv", index=False
    )

    dim = raw.drop_duplicates("customer_id", keep="first").copy()
    dim["age"] = dim["age"].astype(int)
    dim["signup_date"] = pd.to_datetime(dim["signup_date"], format="%Y-%m-%d")

    # A customer cannot order before they exist: pull signup_date back to the
    # first valid order date whenever it falls after it.
    o = orders_dedup.copy()
    o["od"] = pd.to_datetime(o["order_date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    valid = o[o["od"].notna() & (o["customer_id"].str.strip() != "")]
    first_order = valid.groupby("customer_id")["od"].min().rename("first_order_date")

    dim = dim.merge(first_order, on="customer_id", how="left")
    original = dim["signup_date"].copy()
    dim["signup_date"] = dim[["signup_date", "first_order_date"]].min(axis=1)

    changed = dim["signup_date"] < original
    log = pd.DataFrame(
        {
            "customer_id": dim.loc[changed, "customer_id"],
            "signup_date_original": original[changed].dt.strftime("%Y-%m-%d"),
            "first_order_date": dim.loc[changed, "first_order_date"].dt.strftime("%Y-%m-%d"),
            "signup_date_clean": dim.loc[changed, "signup_date"].dt.strftime("%Y-%m-%d"),
            "days_adjusted": (original[changed] - dim.loc[changed, "signup_date"]).dt.days,
        }
    )
    log.to_csv(LOGS / "customer_signup_adjustments_log.csv", index=False)

    dim["signup_date"] = dim["signup_date"].dt.strftime("%Y-%m-%d")
    dim = dim[
        ["customer_id", "customer_name", "gender", "age", "customer_segment", "signup_date"]
    ].sort_values("customer_id")
    dim.to_csv(CLEAN / "dim_customer.csv", index=False)
    return dim, len(raw), int(changed.sum())


# ----------------------------------------------------------------- products
def build_dim_product():
    p = pd.read_csv(RAW / "products_raw.csv", dtype={"product_id": str})
    p["category"] = p["category"].str.strip().str.lower().map(CATEGORY_NAMES)
    assert p["category"].notna().all(), "unexpected category value"

    # Each sub-category belongs to one category. Take the category that most of
    # its products carry and use it to correct the products that disagree.
    counts = p.groupby(["sub_category", "category"]).size().reset_index(name="n")
    reference = (
        counts.sort_values("n", ascending=False)
        .drop_duplicates("sub_category")
        .set_index("sub_category")["category"]
    )
    mismatched = p["category"] != p["sub_category"].map(reference)
    p["category"] = p["sub_category"].map(reference)
    p.to_csv(CLEAN / "dim_product.csv", index=False)
    return p, int(mismatched.sum())


# ------------------------------------------------------------------ regions
def build_dim_region():
    r = pd.read_csv(RAW / "regions_raw.csv", dtype=str)
    r.to_csv(CLEAN / "dim_region.csv", index=False)
    return r


# ------------------------------------------------------------------- orders
def build_fact_sales(orders_dedup):
    o = orders_dedup.copy()

    parsed = pd.to_datetime(o["order_date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    o["is_invalid_date"] = parsed.isna()
    o["order_date"] = parsed.dt.strftime("%Y-%m-%d")  # invalid dates stay blank

    for col in ("customer_id", "product_id"):
        o.loc[o[col].str.strip() == "", col] = None

    o["quantity"] = o["quantity"].astype(int)
    for col in ("discount", "sales_amount", "cost_amount", "profit"):
        o[col] = o[col].astype(float)
    o["is_return"] = o["quantity"] < 0

    n_before = len(o)
    o = o[o["customer_id"].notna() & o["product_id"].notna()]
    n_missing_key = n_before - len(o)

    cols = [
        "order_id", "order_date", "customer_id", "product_id", "region_id",
        "quantity", "discount", "sales_amount", "cost_amount", "profit",
        "is_return", "is_invalid_date",
    ]
    o = o[cols].reset_index(drop=True)
    o.to_csv(CLEAN / "fact_sales.csv", index=False)
    return o, n_missing_key


# --------------------------------------------------------------------- date
def build_dim_date(fact):
    d = pd.Series(pd.to_datetime(fact["order_date"].dropna().unique())).sort_values()
    dim = pd.DataFrame(
        {
            "date_key": d.dt.strftime("%Y%m%d").astype(int),
            "date": d.dt.strftime("%Y-%m-%d"),
            "day": d.dt.day,
            "month": d.dt.month,
            "month_name": d.dt.month_name(),
            "quarter": d.dt.quarter,
            "year": d.dt.year,
        }
    ).reset_index(drop=True)
    dim.to_csv(CLEAN / "dim_date.csv", index=False)
    return dim


def main():
    raw_orders, orders_dedup = load_orders_deduped()
    dim_customer, n_cust_raw, n_signup_fixed = build_dim_customer(orders_dedup)
    dim_product, n_cat_fixed = build_dim_product()
    dim_region = build_dim_region()
    fact, n_missing_key = build_fact_sales(orders_dedup)
    dim_date = build_dim_date(fact)

    # integrity: every key in the fact table resolves to a dimension row
    assert fact["customer_id"].isin(dim_customer["customer_id"]).all()
    assert fact["product_id"].isin(dim_product["product_id"]).all()
    assert fact["region_id"].isin(dim_region["region_id"]).all()
    assert fact["order_date"].dropna().isin(dim_date["date"]).all()
    assert fact["order_id"].is_unique

    print("orders   raw %d -> exact duplicates removed %d -> missing-ID rows removed %d -> fact_sales %d"
          % (len(raw_orders), len(raw_orders) - len(orders_dedup), n_missing_key, len(fact)))
    print("         blank order_date kept: %d | returns flagged: %d"
          % (int(fact["is_invalid_date"].sum()), int(fact["is_return"].sum())))
    print("customer raw %d -> dim_customer %d | signup dates pulled back: %d"
          % (n_cust_raw, len(dim_customer), n_signup_fixed))
    print("product  %d rows | categories corrected: %d" % (len(dim_product), n_cat_fixed))
    print("region   %d rows | dim_date %d rows" % (len(dim_region), len(dim_date)))
    print("totals   sales %.2f | profit %.2f"
          % (fact["sales_amount"].sum(), fact["profit"].sum()))


if __name__ == "__main__":
    main()
