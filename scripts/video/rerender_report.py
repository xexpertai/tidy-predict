"""Re-render report.html from a finished run's run.json (no models are run again: same numbers, same note).
Used after a layout-only change to the report. Usage: python scripts/video/rerender_report.py runs/<id>/out"""
import json
import sys
from pathlib import Path

from tidy_predict.report import render

out = Path(sys.argv[1])
r = json.loads((out / "run.json").read_text())
label = ("Demo data: UCI Online Retail II (real, anonymised orders of a UK online gift shop, CC BY 4.0), "
         "replayed as of 27 Nov 2011")
run_info = {"forecast time": f"{r['forecast_seconds']:.0f} s", "total time": f"{r['total_seconds']:.0f} s",
            "columns": "header rules"}
(out / "report.html").write_text(render(r["facts"], r["note"]["text"], r["note"]["author"], r["clean_stats"], label,
                                        r["actuals"], run_info))
print("re-rendered", out / "report.html")
