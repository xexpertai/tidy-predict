"""Does the local model help when a shop's headers are unusual? Scores header rules alone vs rules + Gemma
on SYNTHETIC header sets (eval/header_variants.json). Needs the local model server running.

A case "works" when every REQUIRED field (date, quantity, and product code or name) is mapped to the right
header and nothing is mapped to a wrong header. Usage: python eval/columns_eval.py eval/results
"""
import json
import sys
from pathlib import Path

from tidy_predict import columns, llm

res = Path(sys.argv[1])
OUTNAME = sys.argv[2] if len(sys.argv) > 2 else "columns_eval.json"
cases = json.loads(Path(__file__).with_name("header_variants.json").read_text())["cases"]
NEED = ("invoice_date", "quantity")


def score(mapping, truth):
    # the product may be keyed by its code or its name: either true product column counts as right
    prod_truth = {truth[f] for f in columns.ONE_OF if f in truth}
    wrong = [f for f, h in mapping.items()
             if (h not in prod_truth if f in columns.ONE_OF else truth.get(f) != h)]
    product_ok = any(mapping.get(f) in prod_truth for f in columns.ONE_OF)
    req_ok = all(mapping.get(f) == truth[f] for f in NEED) and product_ok
    return {"works": req_ok and not wrong, "wrong": wrong,
            "correct_fields": sum(1 for f, h in mapping.items() if truth.get(f) == h), "truth_fields": len(truth)}


if not llm.available():
    sys.exit("start the model server first (scripts/start-model.sh)")
model = llm.model_name()
rows = []
for c in cases:
    h, truth = c["headers"], c["truth"]
    rule = columns.rule_map(h)
    proposed, info = llm.map_columns(h, [c["row"]])
    combined = columns.fill_gaps(rule, proposed, h)           # exactly the app's policy
    alone = columns.fill_gaps({}, proposed, h)
    rows.append({"headers": h, "proposed": proposed, "rules": score(rule, truth),
                 "rules_plus_model": score(combined, truth), "model_alone": score(alone, truth),
                 "model_seconds": info["seconds"]})
    print(h, "rules", rows[-1]["rules"]["works"], "rules+model", rows[-1]["rules_plus_model"]["works"], info["seconds"], "s", flush=True)
summary = {k: sum(r[k]["works"] for r in rows) for k in ("rules", "rules_plus_model", "model_alone")}
out = {"model": model, "cases": len(rows), "works": summary,
       "wrong_mappings": {k: sum(len(r[k]["wrong"]) for r in rows) for k in ("rules", "rules_plus_model", "model_alone")},
       "median_model_seconds": sorted(r["model_seconds"] for r in rows)[len(rows) // 2], "per_case": rows,
       "data_note": "synthetic header sets, see eval/header_variants.json"}
(res / OUTNAME).write_text(json.dumps(out, indent=2))
print(json.dumps({k: out[k] for k in ("model", "cases", "works", "wrong_mappings", "median_model_seconds")}))
