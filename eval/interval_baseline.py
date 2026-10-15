"""Is TabPFN-2's P10-P90 range better than a simple one? Light: no model needed.

Naive range per product and week: take the product's past weeks (up to 52, before the target week),
compute actual / mean-of-previous-4-weeks, and use that ratio's 10th and 90th percentiles times the
current 4-week mean. Compare coverage (want ~80%) and width (narrower is better at the same coverage).
Usage: python eval/interval_baseline.py eval/results
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

res = Path(sys.argv[1])
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True)
pred = pd.read_csv(res / "backtest_predictions.csv", parse_dates=["week"])
lo, hi = [], []
for r in pred.itertuples():
    y = tab[r.product]
    i = tab.index.get_loc(r.week)
    m4 = y.rolling(4).mean().shift(1)
    ratios = (y / m4).iloc[max(5, i - 52):i].replace([np.inf, -np.inf], np.nan).dropna()
    base = m4.iloc[i]
    lo.append(base * np.quantile(ratios, 0.1) if len(ratios) >= 8 else np.nan)
    hi.append(base * np.quantile(ratios, 0.9) if len(ratios) >= 8 else np.nan)
pred["naive_lo"], pred["naive_hi"] = lo, hi
a = pred["actual"]


def stats(l, h):
    ok = l.notna() & h.notna()
    return {"coverage": round(float(((a >= l) & (a <= h))[ok].mean()), 4),
            "above_top_share": round(float((a > h)[ok].mean()), 4),
            "relative_width": round(float((h - l)[ok].sum() / a[ok].sum()), 4), "n": int(ok.sum())}


out = {"tabpfn_p10_p90": stats(pred["p10"], pred["p90"]),
       "naive_ratio_p10_p90": stats(pred["naive_lo"], pred["naive_hi"]),
       "note": "relative_width = sum(top - bottom) / sum(actual); target coverage is 0.80"}
(res / "interval_baseline.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out))
