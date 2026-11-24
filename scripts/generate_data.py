"""
BookNook Books - synthetic data generator (Pakistan, prices in PKR).

Produces three files in ../data/:
  customers.csv   clean customer master (300 rows)
  products.csv    clean product catalogue (150 rows)
  raw_orders.csv  messy checkout export, one row per order line

ALL DATA IS SYNTHETIC. The raw export is deliberately dirty so the ETL
pipeline has real work to do. generation_report.json records exactly how
many problems were injected, so the pipeline's output can be verified.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

N_CUSTOMERS, N_ORDERS = 300, 3000
START, END = pd.Timestamp("2026-04-01"), pd.Timestamp("2026-09-30")
MONTH_MULT = {4: 0.9, 5: 1.0, 6: 0.95, 7: 1.0, 8: 1.3, 9: 1.15}  # August: back-to-school

CITIES = {"Karachi": 22, "Lahore": 20, "Islamabad": 14, "Rawalpindi": 10,
          "Faisalabad": 7, "Multan": 6, "Peshawar": 6, "Sialkot": 4,
          "Quetta": 3, "Hyderabad": 3, "Gujranwala": 3, "Abbottabad": 2}
FIRST = ["Ayesha", "Bilal", "Hina", "Omer", "Sara", "Ahsan", "Mehak", "Usman", "Zara",
         "Hamza", "Noor", "Faizan", "Maryam", "Talha", "Iqra", "Daniyal", "Sana", "Rehan",
         "Laiba", "Hassan", "Fatima", "Saad", "Areeba", "Kamran", "Zainab", "Imran",
         "Rabia", "Waqas", "Nimra", "Adeel"]
LAST = ["Khan", "Malik", "Ahmed", "Siddiqui", "Raza", "Farooq", "Javed", "Butt", "Sheikh",
        "Qureshi", "Iqbal", "Chaudhry", "Hussain", "Rauf", "Mirza", "Nawaz", "Baig",
        "Anwar", "Shah", "Aslam"]
ADJ = ["Silent", "Hidden", "Last", "Golden", "Broken", "Quiet", "Crimson", "Forgotten",
       "Distant", "Midnight", "Hollow", "Burning", "Gentle", "Lost", "Secret", "Winter",
       "Endless", "Fragile", "Bright", "Wandering"]
NOUN = ["Orchard", "Library", "River", "Compass", "Garden", "Letter", "Mountain", "Lantern",
        "Harbour", "Bridge", "Window", "Kingdom", "Season", "Promise", "Shadow", "Voyage",
        "Clock", "Island", "Symphony", "Memory"]
# category: (how many titles, min price, max price) - PKR
CATS = {"Fiction": (30, 700, 1800), "Non-Fiction": (25, 900, 2600),
        "Mystery": (20, 650, 1600), "Sci-Fi": (15, 800, 2000),
        "Children's": (25, 400, 1200), "Biography": (15, 1000, 2800),
        "Self-Help": (12, 700, 1900), "Urdu Literature": (8, 500, 1500)}
STATUSES = ["Completed", "Cancelled", "Pending", "Returned"]
STATUS_P = [0.87, 0.06, 0.03, 0.04]
PAYMENTS = ["Cash on Delivery", "Card", "JazzCash", "Easypaisa"]
PAYMENT_P = [0.55, 0.20, 0.15, 0.10]
STATUS_VARIANTS = {"Completed": ["completed", "COMPLETED", "Completed "],
                   "Cancelled": ["Canceled", "cancelled", "CANCELLED"],
                   "Pending": ["pending", "PENDING"],
                   "Returned": ["returned", "RETURNED"]}


def make_customers():
    rows, used = [], set()
    for i in range(1, N_CUSTOMERS + 1):
        f, l = str(rng.choice(FIRST)), str(rng.choice(LAST))
        email, n = f"{f}.{l}@example.com".lower(), 1
        while email in used:
            n += 1
            email = f"{f}.{l}{n}@example.com".lower()
        used.add(email)
        signup = pd.Timestamp("2025-06-01") + pd.Timedelta(days=int(rng.integers(0, 487)))
        rows.append({"customer_id": i, "first_name": f, "last_name": l, "email": email,
                     "phone": f"03{rng.integers(0, 5)}{rng.integers(0, 10)}-{rng.integers(0, 10**7):07d}",
                     "city": str(rng.choice(list(CITIES), p=np.array(list(CITIES.values())) / 100)),
                     "signup_date": signup.strftime("%Y-%m-%d")})
    return pd.DataFrame(rows)


def make_products():
    rows, titles = [], set()
    for cat, (count, lo, hi) in CATS.items():
        for _ in range(count):
            while True:
                t = f"The {rng.choice(ADJ)} {rng.choice(NOUN)}"
                if t not in titles:
                    titles.add(t)
                    break
            rows.append({"product_name": t, "category": cat,
                         "author": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                         "unit_price": int(round(rng.uniform(lo, hi) / 50) * 50)})
    df = pd.DataFrame(rows)
    df.insert(0, "product_id", range(1, len(df) + 1))
    # popularity: heavy-tailed, cheaper books slightly more popular
    df["pop"] = rng.lognormal(0, 0.8, len(df)) * (1500 / df["unit_price"]) ** 0.3
    return df


def make_orders(customers, products):
    dates = pd.date_range(START, END)
    day_w = np.array([MONTH_MULT[d.month] * (1.25 if d.day_of_week >= 4 else 1.0) for d in dates])
    cust_w = rng.lognormal(0, 1, len(customers))
    cust_w /= cust_w.sum()
    signup = pd.to_datetime(customers["signup_date"]).tolist()
    month_p = {}
    for m in MONTH_MULT:
        w = products["pop"].to_numpy().copy()
        if m == 8:
            w *= np.where(products["category"] == "Children's", 1.8, 1.0)
            w *= np.where(products["category"] == "Non-Fiction", 1.4, 1.0)
        month_p[m] = w / w.sum()

    orders, lines = [], []
    for t in range(N_ORDERS):
        c = int(rng.choice(len(customers), p=cust_w))
        p = day_w * np.array([d >= signup[c] for d in dates])
        d = dates[int(rng.choice(len(dates), p=p / p.sum()))]
        status = str(rng.choice(STATUSES, p=STATUS_P))
        if status == "Pending" and d < pd.Timestamp("2026-09-24"):
            status = "Completed"
        orders.append({"tmp": t, "customer_id": c + 1, "email": customers.at[c, "email"],
                       "date": d, "status": status,
                       "payment_method": str(rng.choice(PAYMENTS, p=PAYMENT_P))})
        n_lines = int(rng.choice([1, 2, 3, 4], p=[0.55, 0.28, 0.12, 0.05]))
        for j in rng.choice(len(products), size=n_lines, replace=False, p=month_p[d.month]):
            lines.append({"tmp": t, "product_id": int(j) + 1,
                          "quantity": int(rng.choice([1, 2, 3], p=[0.8, 0.15, 0.05])),
                          "unit_price": int(products.at[int(j), "unit_price"])})
    orders = pd.DataFrame(orders).sort_values(["date", "tmp"]).reset_index(drop=True)
    orders["order_ref"] = [f"B{5001 + i}" for i in range(len(orders))]
    lines = pd.DataFrame(lines).merge(orders[["tmp", "order_ref"]], on="tmp")
    return orders, lines


def make_raw_export(orders, lines):
    n, report = len(orders), {}
    perm = rng.permutation(n)
    k_unknown, k_nodate = round(0.015 * n), round(0.010 * n)
    unknown, nodate = perm[:k_unknown], perm[k_unknown:k_unknown + k_nodate]

    o = orders.copy()
    # emails: unrecognised (unrecoverable) and messy-but-fixable
    o["raw_email"] = o["email"]
    for i, idx in enumerate(unknown):
        o.at[idx, "raw_email"] = (o.at[idx, "email"].replace("@example.com", "@exmaple.com")
                                  if i % 2 == 0 else f"guest{i}@example.com")
    fixable = (rng.random(n) < 0.06) & ~o.index.isin(unknown)
    for i, idx in enumerate(np.flatnonzero(fixable)):
        e = o.at[idx, "raw_email"]
        o.at[idx, "raw_email"] = e.upper() if i % 2 == 0 else f"  {e} "
    # dates in mixed formats (dd/mm/yyyy, never mm/dd), some missing
    kinds = rng.choice(["iso", "dmy", "dmon"], p=[0.78, 0.12, 0.10], size=n)
    fmts = {"iso": "%Y-%m-%d", "dmy": "%d/%m/%Y", "dmon": "%d-%b-%Y"}
    o["raw_date"] = [d.strftime(fmts[k]) for d, k in zip(o["date"], kinds)]
    o.loc[nodate, "raw_date"] = ""
    # inconsistent status spelling
    variant = rng.random(n) < 0.10
    o["raw_status"] = [str(rng.choice(STATUS_VARIANTS[s])) if v else s
                       for s, v in zip(o["status"], variant)]

    raw = lines.merge(o[["order_ref", "raw_email", "raw_date", "raw_status", "payment_method"]],
                      on="order_ref")
    L = len(raw)
    miss_q = rng.random(L) < 0.004
    bad_q = (rng.random(L) < 0.003) & ~miss_q
    miss_p = rng.random(L) < 0.015
    raw["quantity"] = raw["quantity"].astype("Int64")
    raw.loc[miss_q, "quantity"] = pd.NA
    raw.loc[bad_q, "quantity"] = rng.choice([0, -1], size=bad_q.sum())
    raw.loc[miss_p, "unit_price"] = np.nan
    dups = raw.sample(frac=0.012, random_state=SEED)
    raw = pd.concat([raw, dups]).sort_values("order_ref", kind="stable")

    raw = raw.rename(columns={"raw_email": "customer_email", "raw_date": "order_date",
                              "raw_status": "status"})
    raw = raw[["order_ref", "customer_email", "order_date", "status", "product_id",
               "quantity", "unit_price", "payment_method"]]
    report = {
        "seed": SEED,
        "clean_totals": {"orders": n, "order_lines": L,
                         "gross_revenue_pkr": int((lines.quantity * lines.unit_price).sum())},
        "injected_issues": {
            "orders_unrecognised_email": int(k_unknown),
            "orders_missing_date": int(k_nodate),
            "orders_email_case_or_spaces": int(fixable.sum()),
            "orders_non_iso_date_format": int((kinds != "iso").sum()),
            "orders_status_spelling_variants": int(variant.sum()),
            "lines_missing_quantity": int(miss_q.sum()),
            "lines_zero_or_negative_quantity": int(bad_q.sum()),
            "lines_missing_unit_price_recoverable": int(miss_p.sum()),
            "duplicate_rows_added": int(len(dups)),
        },
        "raw_rows_written": int(len(raw)),
    }
    return raw, report


if __name__ == "__main__":
    customers, products = make_customers(), make_products()
    orders, lines = make_orders(customers, products)
    raw, report = make_raw_export(orders, lines)

    customers.to_csv(OUT / "customers.csv", index=False)
    products.drop(columns="pop").to_csv(OUT / "products.csv", index=False)
    raw.to_csv(OUT / "raw_orders.csv", index=False)
    (OUT / "generation_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
