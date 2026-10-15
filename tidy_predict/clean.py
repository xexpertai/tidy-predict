"""Clean a messy order export into demand lines, and say why every dropped row was dropped.

Nothing is silently deleted: each row that does not count as demand gets a reason in
``CleanResult.issues``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Stock codes that are not products (postage, fees, manual adjustments...). Rows whose code has no
# digit at all are treated the same way (e.g. "POST", "DOT", "M", "BANK CHARGES").
SERVICE_PREFIXES = ("TEST", "GIFT_", "ADJUST", "AMAZONFEE", "BANK CHARGES", "C2")

REASONS = {
    "duplicate": "exact duplicate of an earlier row",
    "bad_date": "date could not be read",
    "bad_quantity": "quantity is not a number",
    "no_product": "no product code or name",
    "service_line": "not a product (postage, fee or manual adjustment)",
    "cancellation": "cancellation / return line",
    "cancelled_sale": "sale that a later cancellation undoes",
    "zero_price": "price is zero or negative (free item or correction)",
    "zero_quantity": "quantity is zero",
}


@dataclass
class CleanResult:
    lines: pd.DataFrame                 # demand lines: invoice_date, product, description, quantity, price
    issues: pd.DataFrame                # source_row, reason, detail
    stats: dict = field(default_factory=dict)


def _ws(s: pd.Series) -> pd.Series:
    return s.astype("string[pyarrow]").str.replace(r"\s+", " ", regex=True).str.strip()


def _parse_dates(s: pd.Series) -> pd.Series:
    s = _ws(s)
    out = pd.to_datetime(s, errors="coerce", format="ISO8601")
    todo = out.isna() & s.notna()
    if todo.any():
        # Day-first is the common case outside the US; try it, then month-first, then Excel serials.
        for kw in ({"dayfirst": True}, {"dayfirst": False}):
            if not todo.any():
                break
            got = pd.to_datetime(s[todo], errors="coerce", format="mixed", **kw)
            out[todo] = got
            todo = out.isna() & s.notna()
        if todo.any():
            num = pd.to_numeric(s[todo], errors="coerce")
            serial = (num > 20000) & (num < 80000)
            out.loc[serial[serial].index] = pd.to_datetime("1899-12-30") + pd.to_timedelta(num[serial], unit="D")
    return out


def _parse_number(s: pd.Series) -> pd.Series:
    t = _ws(s).str.replace(r"[,\s]", "", regex=True).str.replace(r"^[^\d\-+.]+", "", regex=True)
    return pd.to_numeric(t, errors="coerce")


def _is_service(code: pd.Series) -> pd.Series:
    c = code.fillna("").str.upper()
    no_digit = ~c.str.contains(r"\d", regex=True) & (c != "")
    return no_digit | c.str.startswith(SERVICE_PREFIXES)


def _match_cancellations(df: pd.DataFrame, is_cancel: pd.Series) -> set:
    """Each cancellation undoes the most recent earlier sale with the same customer, product and
    quantity. If two cancellations point at the same sale, only the first one removes it."""
    c = df.loc[is_cancel & df["customer_id"].notna(), ["date", "customer_id", "product", "qty"]]
    s = df.loc[~is_cancel & (df["qty"] > 0) & df["customer_id"].notna(), ["date", "customer_id", "product", "qty"]]
    if c.empty or s.empty:
        return set()
    c = c.assign(key=c["customer_id"].astype(str) + "|" + c["product"].astype(str) + "|" + (-c["qty"]).astype(str))
    s = s.assign(key=s["customer_id"].astype(str) + "|" + s["product"].astype(str) + "|" + s["qty"].astype(str),
                 sale_idx=s.index)
    m = pd.merge_asof(c.sort_values("date")[["date", "key"]], s.sort_values("date")[["date", "key", "sale_idx"]],
                      on="date", by="key", direction="backward")
    return set(m["sale_idx"].dropna().astype(int).drop_duplicates())


def clean_orders(raw: pd.DataFrame, mapping: dict[str, str]) -> CleanResult:
    """``mapping`` is {canonical field: header in ``raw``} (see columns.py)."""
    df = pd.DataFrame({"source_row": np.arange(len(raw)) + 2})  # +2: header is row 1 in a sheet
    for f in ("invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id"):
        df[f] = _ws(raw[mapping[f]]) if f in mapping else pd.Series(pd.NA, index=raw.index, dtype="string")
    issues: list[pd.DataFrame] = []
    stats: dict = {"rows_in": int(len(df))}

    def drop(mask: pd.Series, reason: str, detail: pd.Series | None = None) -> None:
        nonlocal df
        mask = mask.fillna(False).astype(bool)
        if mask.any():
            d = df.loc[mask]
            issues.append(pd.DataFrame({
                "source_row": d["source_row"].values,
                "reason": reason,
                "detail": (detail[mask].astype(str).values if detail is not None else REASONS[reason]),
            }))
        stats[reason] = int(mask.sum())
        df = df.loc[~mask]

    key_cols = ["invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id"]
    drop(df.duplicated(subset=key_cols, keep="first"), "duplicate")

    df["date"] = _parse_dates(df["invoice_date"])
    drop(df["date"].isna(), "bad_date", "could not read: " + df["invoice_date"].fillna("<blank>"))
    df["qty"] = _parse_number(df["quantity"])
    drop(df["qty"].isna(), "bad_quantity", "could not read: " + df["quantity"].fillna("<blank>"))
    df["unit_price"] = _parse_number(df["price"])

    df["product"] = df["stock_code"].str.upper()
    df.loc[df["product"].isna() | (df["product"] == ""), "product"] = df["description"].str.upper()
    drop(df["product"].isna() | (df["product"] == ""), "no_product")
    drop(_is_service(df["stock_code"]), "service_line", "code " + df["stock_code"].fillna(""))

    inv = df["invoice"].fillna("")
    is_cancel = inv.str.upper().str.startswith("C") | (df["qty"] < 0)
    undone = _match_cancellations(df, is_cancel)
    drop(is_cancel, "cancellation")
    drop(df.index.to_series().isin(undone), "cancelled_sale")
    drop(df["unit_price"].notna() & (df["unit_price"] <= 0), "zero_price")
    drop(df["qty"] == 0, "zero_quantity")

    lines = df.rename(columns={"date": "invoice_date_parsed"})[
        ["source_row", "invoice_date_parsed", "product", "description", "qty", "unit_price", "invoice", "customer_id"]
    ].rename(columns={"invoice_date_parsed": "date", "qty": "quantity", "unit_price": "price"})
    stats["rows_out"] = int(len(lines))
    stats["products"] = int(lines["product"].nunique())
    iss = (pd.concat(issues, ignore_index=True) if issues
           else pd.DataFrame(columns=["source_row", "reason", "detail"]))
    return CleanResult(lines=lines.reset_index(drop=True), issues=iss.sort_values("source_row", kind="stable"), stats=stats)


def product_names(lines: pd.DataFrame) -> dict[str, str]:
    """Most common description per product code, for readable output."""
    d = lines.dropna(subset=["description"])
    if d.empty:
        return {}
    return d.groupby("product")["description"].agg(lambda s: s.value_counts().index[0]).to_dict()


def tidy_name(name: str) -> str:
    """'WHITE HANGING HEART T-LIGHT HOLDER' -> 'White hanging heart t-light holder'."""
    s = re.sub(r"\s+", " ", str(name)).strip().lower()
    return s[:1].upper() + s[1:]
