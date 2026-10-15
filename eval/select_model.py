"""Model selection on VALIDATION weeks only (Jul-Aug 2011), before the final test weeks are run.

Compares two ways of framing the TabPFN-2 target, with the baselines alongside for context.
Usage: python eval/select_model.py eval/results
"""
import json
import sys
from pathlib import Path

import pandas as pd

from tidy_predict.forecast import naive_forecasts, tabpfn_forecast, wape
from tidy_predict.weekly import pick_products

res = Path(sys.argv[1])
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True)
tab.index.name = "week"
val = tab.index[(tab.index >= "2011-07-04") & (tab.index <= "2011-08-15")]  # 7 weeks, all before the test weeks
rows = []
for wk in val:
    prods = pick_products(tab, wk, n=20)
    nv = naive_forecasts(tab, prods, wk)
    r = {"week": str(wk.date())}
    for name, rel in (("level", False), ("relative", True)):
        f = tabpfn_forecast(tab, prods, wk, relative=rel)
        r[f"tabpfn_{name}"] = wape(f.table.actual, f.table.p50)
        r[f"seconds_{name}"] = round(f.seconds, 1)
    r["last_week"] = wape(nv.actual, nv.last_week)
    r["mean_4w"] = wape(nv.actual, nv.mean_4w)
    rows.append(r)
    print(r, flush=True)
df = pd.DataFrame(rows)
summary = {c: round(float(df[c].mean()), 4) for c in df.columns if c != "week"}
(res / "model_selection.json").write_text(json.dumps({"validation_weeks": df["week"].tolist(),
    "per_week": rows, "mean_weekly_wape": summary}, indent=2))
print(summary)
