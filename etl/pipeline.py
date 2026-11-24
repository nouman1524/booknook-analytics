"""
BookNook ETL pipeline: extract -> transform -> load.

Run from the project root:
    python -m etl.pipeline --reset      # drop + recreate tables, then load

Cleans data/raw_orders.csv and loads customers, products, orders and
order_items into PostgreSQL in ONE transaction (all-or-nothing).
Every dropped row is written to reports/rejected_rows.csv with a reason,
and a run summary goes to reports/etl_run_summary.json.
"""
import argparse
import json
import logging

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func, select, text

import config
from etl.models import customers, metadata, order_items, orders, products

log = logging.getLogger("booknook.etl")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y")  # day-first: this is a Pakistani export
VALID_STATUSES = {"Completed", "Cancelled", "Pending", "Returned"}


# ---------------------------------------------------------------- extract
def extract():
    raw = pd.read_csv(config.DATA_DIR / "raw_orders.csv", dtype=str)
    cust = pd.read_csv(config.DATA_DIR / "customers.csv")
    prod = pd.read_csv(config.DATA_DIR / "products.csv")
    log.info("EXTRACT  raw_orders=%d rows, customers=%d, products=%d", len(raw), len(cust), len(prod))
    return raw, cust, prod


# -------------------------------------------------------------- transform
def parse_dates(series):
    """Try each known format in turn; anything left over becomes NaT."""
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = parsed.isna() & series.notna()
        parsed[todo] = pd.to_datetime(series[todo], format=fmt, errors="coerce")
    return parsed


def transform(raw, cust, prod):
    stats = {"raw_rows": len(raw)}

    df = raw.drop_duplicates().copy()
    stats["exact_duplicate_rows_removed"] = len(raw) - len(df)

    df["customer_email"] = df["customer_email"].str.strip().str.lower()
    df["status"] = df["status"].str.strip().str.title().replace({"Canceled": "Cancelled"})
    df["order_date"] = parse_dates(df["order_date"].str.strip().replace("", np.nan))
    for col in ("product_id", "quantity", "unit_price"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    email_to_id = dict(zip(cust["email"].str.lower(), cust["customer_id"]))
    df["customer_id"] = df["customer_email"].map(email_to_id)
    price_missing = df["unit_price"].isna()
    df["unit_price"] = df["unit_price"].fillna(df["product_id"].map(dict(zip(prod.product_id, prod.unit_price))))

    # First failing rule wins, so each rejected row carries exactly one reason.
    df["reject_reason"] = np.select(
        [df["order_date"].isna(),
         df["customer_id"].isna(),
         ~df["status"].isin(VALID_STATUSES),
         df["unit_price"].isna(),
         df["quantity"].isna(),
         df["quantity"] <= 0],
        ["missing_or_invalid_date", "unrecognised_email", "invalid_status",
         "unknown_product", "missing_quantity", "non_positive_quantity"],
        default="",
    )
    rejects, good = df[df["reject_reason"] != ""], df[df["reject_reason"] == ""].copy()
    stats["rows_rejected"] = len(rejects)
    stats["rejected_rows_by_reason"] = rejects["reject_reason"].value_counts().to_dict()
    stats["rejected_orders_by_reason"] = rejects.groupby("reject_reason")["order_ref"].nunique().to_dict()
    stats["unit_prices_recovered_from_catalogue"] = int((price_missing & (df["reject_reason"] == "")).sum())
    stats["email_normalised_rows"] = int((raw.drop_duplicates()["customer_email"] !=
                                          df["customer_email"].reindex(raw.drop_duplicates().index)).sum())

    # Orders that are internally inconsistent would corrupt the orders table.
    order_cols = ["customer_id", "order_date", "status", "payment_method"]
    if good.groupby("order_ref")[order_cols].nunique().max().max() > 1:
        raise ValueError("an order_ref has conflicting header values across its lines")

    orders_df = (good.groupby("order_ref", as_index=False)[order_cols].first()
                 .assign(customer_id=lambda d: d["customer_id"].astype(int),
                         order_date=lambda d: d["order_date"].dt.date))
    items_df = good[["order_ref", "product_id", "quantity", "unit_price"]].astype(
        {"product_id": int, "quantity": int, "unit_price": float})
    if items_df.duplicated(["order_ref", "product_id"]).any():
        raise ValueError("duplicate product within one order after cleaning")

    stats["orders_to_load"], stats["order_items_to_load"] = len(orders_df), len(items_df)
    stats["revenue_to_load_pkr"] = float((items_df["quantity"] * items_df["unit_price"]).sum())
    log.info("TRANSFORM  rows %d -> %d clean | rejected %d %s | dedup removed %d",
             len(raw), len(good), len(rejects), stats["rejected_rows_by_reason"],
             stats["exact_duplicate_rows_removed"])
    return orders_df, items_df, rejects, stats


# ------------------------------------------------------------------- load
def load(engine, orders_df, items_df, cust, prod, reset=False):
    cust = cust.assign(signup_date=pd.to_datetime(cust["signup_date"]).dt.date)
    with engine.begin() as conn:                       # single transaction
        if reset:
            metadata.drop_all(conn)
        metadata.create_all(conn)
        if conn.execute(select(func.count()).select_from(orders)).scalar():
            raise RuntimeError("orders table is not empty - rerun with --reset")

        conn.execute(customers.insert(), cust.to_dict("records"))
        conn.execute(products.insert(), prod.to_dict("records"))
        if conn.dialect.name == "postgresql":          # explicit IDs were inserted: resync serials
            for tbl, col in ((customers, "customer_id"), (products, "product_id")):
                conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl.name}','{col}'), "
                                  f"(SELECT MAX({col}) FROM {tbl.name}))"))

        conn.execute(orders.insert(), orders_df.to_dict("records"))
        ref_to_id = dict(conn.execute(select(orders.c.order_ref, orders.c.order_id)).all())
        items = items_df.assign(order_id=items_df["order_ref"].map(ref_to_id)).drop(columns="order_ref")
        conn.execute(order_items.insert(), items.to_dict("records"))

        counts = {t.name: conn.execute(select(func.count()).select_from(t)).scalar()
                  for t in (customers, products, orders, order_items)}
        if counts["orders"] != len(orders_df) or counts["order_items"] != len(items_df):
            raise RuntimeError(f"row-count mismatch after load: {counts}")  # rolls back
    log.info("LOAD  committed: %s", counts)
    return counts


# -------------------------------------------------------------------- run
def run_pipeline(reset=False):
    config.REPORT_DIR.mkdir(exist_ok=True)
    raw, cust, prod = extract()
    orders_df, items_df, rejects, stats = transform(raw, cust, prod)
    rejects.drop(columns=["customer_id"]).to_csv(config.REPORT_DIR / "rejected_rows.csv", index=False)
    stats["rows_loaded"] = load(create_engine(config.DATABASE_URL), orders_df, items_df, cust, prod, reset)
    (config.REPORT_DIR / "etl_run_summary.json").write_text(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="BookNook ETL pipeline")
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    run_pipeline(ap.parse_args().reset)
