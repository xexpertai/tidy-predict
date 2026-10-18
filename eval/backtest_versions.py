"""Side-by-side check on the SAME 12 held-out weeks and 240 product-weeks as backtest.py:
TabPFN-2 (shipped, commercial-OK) vs newer TabPFN versions (non-commercial licence, evaluation only).
Also scores the "chance of selling out" (P(demand > stock)) against what really happened.

Stock rule used for the check (the data has no real stock levels): the shop stocks its 4-week average.

Usage: python eval/backtest_versions.py eval/results v2 v3.5
"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from tidy_predict.forecast import QCOLS, chance_demand_above, naive_forecasts, tabpfn_forecast, wape
from tidy_predict.weekly import pick_products

res = Path(sys.argv[1]); versions = sys.argv[2:] or ["v2"]
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True); tab.index.name = "week"
targets = tab.index[-12:]
for ver in versions:
    rows = []
    for wk in targets:
        prods = pick_products(tab, wk, n=20)
        fc = tabpfn_forecast(tab, prods, wk, version=ver)
        nv = naive_forecasts(tab, prods, wk)[["product", "mean_4w"]]
        df = fc.table.merge(nv, on="product")
        df["p_sellout"] = [chance_demand_above(r, r["mean_4w"]) for _, r in df.iterrows()]
        rows.append(df); print(ver, wk.date(), f"{fc.seconds:.0f}s", flush=True)
    d = pd.concat(rows, ignore_index=True); d.to_csv(res / f"backtest_{ver}.csv", index=False)
