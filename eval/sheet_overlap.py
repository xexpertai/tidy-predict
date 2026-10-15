"""Source the claim "the demo file's two Excel sheets overlap": count the rows of the second sheet that fall
inside the first sheet's date range, and how many of those are exact copies of a first-sheet row.
Usage: python eval/sheet_overlap.py data/raw/online_retail_II.xlsx eval/results"""
import json
import sys
from pathlib import Path

import pandas as pd

src, R = Path(sys.argv[1]), Path(sys.argv[2])
sheets = pd.read_excel(src, sheet_name=None, engine="calamine", dtype=str)
(n1, s1), (n2, s2) = list(sheets.items())
for s in (s1, s2):
    s["_d"] = pd.to_datetime(s["InvoiceDate"], errors="coerce")
end1 = s1["_d"].max()
in_overlap = s2[s2["_d"] <= end1]
key = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
norm = lambda d: d[key].fillna("").astype(str).apply(lambda c: c.str.replace(r"\.0$", "", regex=True))  # noqa: E731
copies = norm(in_overlap).merge(norm(s1).drop_duplicates(), on=key, how="inner")
out = {"sheet_1": n1, "sheet_1_rows": len(s1), "sheet_1_dates": [str(s1["_d"].min()), str(end1)],
       "sheet_2": n2, "sheet_2_rows": len(s2), "sheet_2_dates": [str(s2["_d"].min()), str(s2["_d"].max())],
       "sheet_2_rows_inside_sheet_1_dates": len(in_overlap),
       "of_which_exact_copies_of_a_sheet_1_row": len(copies),
       "total_duplicates_removed_by_cleaning": json.loads((R / "clean_stats.json").read_text())["stats"]["duplicate"]}
(R / "sheet_overlap.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=1))
