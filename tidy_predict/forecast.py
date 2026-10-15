"""Next-week units per product with TabPFN-2 (Built with PriorLabs-TabPFN), plus simple baselines.

Only the TabPFN-2 weights are ever loaded (``ModelVersion.V2``): they are under the Prior Labs
License (Apache 2.0 + attribution), which allows commercial use. That matters for a paid side
hustle. Newer TabPFN weights are non-commercial only.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .weekly import FEATURES, feature_rows

RELATIVE = False          # chosen on validation weeks, see eval/select_model.py
MAX_TRAIN = 1000          # TabPFN-2's CPU guardrail; we keep the most recent rows
QUANTILES = (0.1, 0.5, 0.9)


@dataclass
class Forecast:
    table: pd.DataFrame   # product, week, mean, p10, p50, p90 (+ actual when known)
    seconds: float
    n_train: int


def _train_rows(tab: pd.DataFrame, products: list[str], target_week: pd.Timestamp) -> pd.DataFrame:
    weeks = tab.index[tab.index < target_week]
    tr = feature_rows(tab, products, weeks)
    return tr.sort_values("week").tail(MAX_TRAIN)


def _relative(df: pd.DataFrame) -> pd.DataFrame:
    """Express lags and target relative to the product's recent level (log space), so one model can
    learn from best-sellers and slow sellers at once."""
    out = df.copy()
    for c in FEATURES:
        if c.startswith("lag") or c in ("mean4", "mean26"):
            out[c] = df[c] - df["mean8"]
    if "target" in out:
        out["target"] = df["target"] - df["mean8"]
    return out


def tabpfn_forecast(tab: pd.DataFrame, products: list[str], target_week: pd.Timestamp,
                    n_estimators: int = 4, seed: int = 0, relative: bool = RELATIVE) -> Forecast:
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion

    t0 = time.time()
    tr = _train_rows(tab, products, target_week)
    te = feature_rows(tab, products, [target_week])
    reg = TabPFNRegressor.create_default_for_version(
        ModelVersion.V2, device="cpu", n_estimators=n_estimators, random_state=seed)
    base = te["mean8"].to_numpy() if relative else 0.0
    if relative:
        tr, te_x = _relative(tr), _relative(te)
    else:
        te_x = te
    reg.fit(tr[FEATURES].to_numpy(np.float32), tr["target"].to_numpy(np.float32))
    full = reg.predict(te_x[FEATURES].to_numpy(np.float32), output_type="main", quantiles=list(QUANTILES))
    out = te[["product", "week", "actual"]].copy()
    out["mean"] = np.clip(np.expm1(full["mean"] + base), 0, None)
    for q, arr in zip(QUANTILES, full["quantiles"]):
        out[f"p{int(q * 100)}"] = np.clip(np.expm1(arr + base), 0, None)
    return Forecast(table=out.reset_index(drop=True), seconds=time.time() - t0, n_train=len(tr))


def gbm_forecast(tab: pd.DataFrame, products: list[str], target_week: pd.Timestamp, seed: int = 0) -> pd.DataFrame:
    """A tuned-by-default tree model on the same features, as a fair non-foundation baseline."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    tr = _train_rows(tab, products, target_week)
    te = feature_rows(tab, products, [target_week])
    m = HistGradientBoostingRegressor(random_state=seed).fit(tr[FEATURES], tr["target"])
    out = te[["product", "week", "actual"]].copy()
    out["mean"] = np.clip(np.expm1(m.predict(te[FEATURES])), 0, None)
    return out.reset_index(drop=True)


def naive_forecasts(tab: pd.DataFrame, products: list[str], target_week: pd.Timestamp) -> pd.DataFrame:
    """last week / mean of last 4 weeks / same week last year."""
    i = tab.index.get_loc(target_week)
    rows = []
    for p in products:
        y = tab[p].to_numpy()
        rows.append({
            "product": p, "week": target_week, "actual": y[i],
            "last_week": y[i - 1],
            "mean_4w": y[i - 4:i].mean(),
            "same_week_last_year": y[i - 52] if i >= 52 else np.nan,
        })
    return pd.DataFrame(rows)


def wape(actual, pred) -> float:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    m = ~np.isnan(p)
    return float(np.abs(a[m] - p[m]).sum() / max(a[m].sum(), 1e-9))
