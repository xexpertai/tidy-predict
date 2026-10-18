"""Score 'chance of selling out' (P(demand > 4-week-average stock)) on the 240 held-out product-weeks.
Usage: python eval/sellout_calibration.py eval/results v2 [v3.5]  -> eval/results/sellout_<v>.json"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

res = Path(sys.argv[1])
for ver in sys.argv[2:]:
    d = pd.read_csv(res / f"backtest_{ver}.csv")
    hit = (d["actual"] > d["mean_4w"]).astype(float)       # demand really went above the 4-week-average stock
    p = d["p_sellout"]
    out = {"version": ver, "n": int(len(d)), "mean_predicted": round(float(p.mean()), 3), "share_really_above": round(float(hit.mean()), 3),
           "brier": round(float(((p - hit) ** 2).mean()), 4),
           "brier_always_base_rate": round(float(((hit.mean() - hit) ** 2).mean()), 4),
           "brier_coin_flip": round(float(((0.5 - hit) ** 2).mean()), 4)}
    bins = [(0, .25), (.25, .5), (.5, .75), (.75, 1.01)]
    rows = []
    for lo, hi in bins:
        m = (p >= lo) & (p < hi)
        rows.append({"predicted_range": f"{int(lo*100)}-{min(int(hi*100),100)}%", "n": int(m.sum()),
                     "mean_predicted_pct": round(float(p[m].mean() * 100), 1) if m.any() else None,
                     "really_sold_above_pct": round(float(hit[m].mean() * 100), 1) if m.any() else None})
    out["bins"] = rows
    hi_m = p >= 0.5
    out["flagged_50plus"] = {"n": int(hi_m.sum()), "really_above": int(hit[hi_m].sum())}
    # rank quality: is the flagged top third more often above?
    top = p.rank(pct=True) > 2 / 3
    out["top_third_really_above_pct"] = round(float(hit[top].mean() * 100), 1)
    out["bottom_third_really_above_pct"] = round(float(hit[p.rank(pct=True) <= 1 / 3].mean() * 100), 1)
    (res / f"sellout_{ver}.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
