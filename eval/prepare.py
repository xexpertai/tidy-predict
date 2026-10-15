"""Step 1 of the evaluation: clean the public demo export and save the weekly units table.

Usage: python eval/prepare.py data/raw/online_retail_II.csv eval/results
"""
import json
import sys
from pathlib import Path

import pandas as pd

from tidy_predict.clean import clean_orders, product_names
from tidy_predict.cli import read_table, resolve_columns
from tidy_predict.weekly import weekly_units

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
raw = read_table(src)
mapping, _ = resolve_columns(raw, False, print)
cr = clean_orders(raw, mapping)
tab = weekly_units(cr.lines)
tab.to_csv(out / "weekly_units.csv.gz")
pd.Series(product_names(cr.lines)).rename("description").to_csv(out / "product_names.csv.gz")
svc = cr.issues[cr.issues["reason"] == "service_line"]["detail"].value_counts()
(out / "clean_stats.json").write_text(json.dumps({
    "source": src.name, "stats": cr.stats,
    "first_day": str(cr.lines["date"].min()), "last_day": str(cr.lines["date"].max()),
    "weeks": len(tab), "first_week": str(tab.index[0].date()), "last_full_week": str(tab.index[-1].date()),
    "service_codes_set_aside": svc.to_dict(),
}, indent=2))
print(json.dumps(cr.stats))
