"""How often does the local model's note pass the number check? One note per backtest week.

Builds the same facts the app builds (from eval/results/backtest_predictions.csv and the weekly table),
asks the local model for the note, and records every attempt: passed first time, passed on the retry,
or replaced by the template. Needs the model server running.
Usage: python eval/note_eval.py eval/results
"""
import json
import sys
from pathlib import Path

import pandas as pd

from tidy_predict import llm
from tidy_predict.note import build_facts, write_note

res = Path(sys.argv[1])
if not llm.available():
    sys.exit("start the model server first (scripts/start-model.sh)")
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True)
names = pd.read_csv(res / "product_names.csv.gz", index_col=0)["description"].to_dict()
stats = json.loads((res / "clean_stats.json").read_text())["stats"]
pred = pd.read_csv(res / "backtest_predictions.csv", parse_dates=["week"])

rows = []
for wk, g in pred.groupby("week"):
    facts = build_facts(g, names, wk, stats, tab.loc[tab.index < wk])
    n = write_note(facts)
    first_ok = bool(n.attempts and n.attempts[0].get("ok"))
    outcome = ("passed first time" if first_ok else
               "passed on retry" if n.author != "template" else "template fallback")
    rows.append({"week": str(wk.date()), "outcome": outcome, "author": n.author, "note": n.text,
                 "attempts": n.attempts})
    print(wk.date(), outcome, [a.get("unknown_numbers") for a in n.attempts], flush=True)

counts = pd.Series([r["outcome"] for r in rows]).value_counts().to_dict()
secs = [a.get("seconds") for r in rows for a in r["attempts"] if a.get("seconds")]
out = {"model": llm.model_name(), "notes": len(rows), "outcomes": counts,
       "drafts": sum(len(r["attempts"]) for r in rows),
       "drafts_rejected": sum(1 for r in rows for a in r["attempts"] if a.get("ok") is False),
       "median_seconds_per_draft": sorted(secs)[len(secs) // 2] if secs else None,
       "per_week": rows}
(res / "note_eval.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "per_week"}))
