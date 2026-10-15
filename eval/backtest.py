"""Step 2 of the evaluation: rolling one-week-ahead backtest on the public demo data.

For each of the last N full weeks: pretend it is the Sunday before, pick the 20 regular sellers
using only earlier weeks, forecast that week with TabPFN-2 and with simple baselines, then compare
with what was actually sold. All numbers in the README come from the files this writes.

Usage: python eval/backtest.py eval/results [N_WEEKS]
"""
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from tidy_predict.forecast import gbm_forecast, naive_forecasts, tabpfn_forecast, wape
from tidy_predict.weekly import pick_products

res = Path(sys.argv[1])
n_weeks = int(sys.argv[2]) if len(sys.argv) > 2 else 12
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True)
tab.index.name = "week"
targets = tab.index[-n_weeks:]

rows, timing = [], []
for wk in targets:
    prods = pick_products(tab, wk, n=20)
    fc = tabpfn_forecast(tab, prods, wk)
    gb = gbm_forecast(tab, prods, wk)
    nv = naive_forecasts(tab, prods, wk)
    df = fc.table.merge(gb[["product", "mean"]].rename(columns={"mean": "gbm"}), on="product") \
                 .merge(nv.drop(columns=["actual", "week"]), on="product")
    rows.append(df)
    timing.append({"week": str(wk.date()), "tabpfn_seconds": round(fc.seconds, 1), "n_train": fc.n_train})
    print(f"{wk.date()}  tabpfn {fc.seconds:5.1f}s  wape p50 {wape(df.actual, df.p50):.3f}  "
          f"last_week {wape(df.actual, df.last_week):.3f}  gbm {wape(df.actual, df.gbm):.3f}", flush=True)

allp = pd.concat(rows, ignore_index=True)
allp.to_csv(res / "backtest_predictions.csv", index=False)

methods = {
    "TabPFN-2 median": "p50", "TabPFN-2 mean": "mean", "Gradient boosting (same features)": "gbm",
    "Last week": "last_week", "Mean of last 4 weeks": "mean_4w", "Same week last year": "same_week_last_year",
}
a = allp["actual"].to_numpy()
summary = {}
for name, col in methods.items():
    p = allp[col].to_numpy(float)
    m = ~np.isnan(p)
    weekly = [wape(g["actual"], g[col]) for _, g in allp.groupby("week")]
    summary[name] = {
        "wape": round(wape(a, p), 4),
        "mae_units": round(float(np.abs(a[m] - p[m]).mean()), 1),
        "weeks_best_or_tied": None,
        "median_weekly_wape": round(float(np.nanmedian(weekly)), 4),
        "n": int(m.sum()),
    }
# how often each method had the lowest WAPE in a week
per_week = pd.DataFrame({name: [wape(g["actual"], g[col]) for _, g in allp.groupby("week")] for name, col in methods.items()
                         if name != "TabPFN-2 mean"})
best = per_week.idxmin(axis=1).value_counts()
for name in summary:
    summary[name]["weeks_best_or_tied"] = int(best.get(name, 0))

inside = (allp["actual"] >= allp["p10"]) & (allp["actual"] <= allp["p90"])
out = {
    "data": "UCI Online Retail II (CC BY 4.0), cleaned by tidy-predict",
    "weeks": [str(w.date()) for w in targets], "products_per_week": 20, "predictions": int(len(allp)),
    "metric_note": "WAPE = sum|actual - forecast| / sum(actual), pooled over all product-weeks; lower is better.",
    "summary": summary,
    "tabpfn_interval": {
        "p10_p90_coverage": round(float(inside.mean()), 4),
        "actual_above_p90_share": round(float((allp["actual"] > allp["p90"]).mean()), 4),
        "actual_below_p10_share": round(float((allp["actual"] < allp["p10"]).mean()), 4),
    },
    "timing": timing,
    "tabpfn_seconds_median": float(np.median([t["tabpfn_seconds"] for t in timing])),
    "machine": {"cpu": platform.processor() or platform.machine(), "python": platform.python_version()},
    "generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
}
(res / "backtest_summary.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out["summary"], indent=1))
print(json.dumps(out["tabpfn_interval"]))
