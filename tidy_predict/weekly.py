"""Turn clean demand lines into a weekly units table and one feature row per (product, week)."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 2, 3, 4, 52)


def week_start(d: pd.Series) -> pd.Series:
    """Monday of the week each date falls in."""
    d = pd.to_datetime(d).dt.normalize()
    return d - pd.to_timedelta(d.dt.weekday, unit="D")


def weekly_units(lines: pd.DataFrame, until: pd.Timestamp | None = None) -> pd.DataFrame:
    """Wide table: index = week (Monday), columns = product, values = units sold (0 if none).

    Only full weeks are kept: if ``until`` (the last day of data, inclusive) is mid-week, that week
    is dropped so a half week never looks like a slump.
    """
    w = lines.assign(week=week_start(lines["date"]))
    tab = w.pivot_table(index="week", columns="product", values="quantity", aggfunc="sum", fill_value=0)
    full = pd.date_range(tab.index.min(), tab.index.max(), freq="W-MON")
    tab = tab.reindex(full, fill_value=0)
    tab.index.name = "week"
    last_day = pd.Timestamp(until) if until is not None else lines["date"].max().normalize()
    if tab.index[-1] + pd.Timedelta(days=6) > last_day:
        tab = tab.iloc[:-1]
    return tab.astype(float)


def pick_products(tab: pd.DataFrame, before: pd.Timestamp, n: int = 20, window: int = 26,
                  min_weeks: int = 20) -> list[str]:
    """Regular sellers: sold in at least ``min_weeks`` of the last ``window`` weeks before ``before``;
    the ``n`` with the most units in that window."""
    recent = tab.loc[tab.index < before].tail(window)
    regular = (recent > 0).sum() >= min_weeks
    return recent.loc[:, regular].sum().sort_values(ascending=False).head(n).index.tolist()


def feature_rows(tab: pd.DataFrame, products: list[str], weeks: list[pd.Timestamp] | pd.DatetimeIndex) -> pd.DataFrame:
    """One row per (product, target week) using only information from before that week."""
    rows = []
    idx = {w: i for i, w in enumerate(tab.index)}
    for p in products:
        y = tab[p].to_numpy()
        first = int(np.argmax(y > 0)) if (y > 0).any() else len(y)
        for wk in weeks:
            i = idx.get(pd.Timestamp(wk))
            if i is None or i < 8 or i - 4 < first:
                continue
            hist = y[:i]
            r = {"product": p, "week": tab.index[i]}
            for L in LAGS:
                r[f"lag{L}"] = np.log1p(hist[i - L]) if i - L >= first else np.nan
            r["mean4"] = np.log1p(hist[i - 4:i].mean())
            r["mean8"] = np.log1p(hist[i - 8:i].mean())
            r["mean26"] = np.log1p(hist[max(first, i - 26):i].mean())
            r["zero_share8"] = float((hist[i - 8:i] == 0).mean())
            r["week_of_year"] = int(tab.index[i].isocalendar().week)
            r["target"] = np.log1p(y[i])
            r["actual"] = y[i]
            rows.append(r)
    return pd.DataFrame(rows)


FEATURES = [f"lag{L}" for L in LAGS] + ["mean4", "mean8", "mean26", "zero_share8", "week_of_year"]
