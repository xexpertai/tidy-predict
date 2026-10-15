"""tidy-predict: messy order export in, restock note out. Everything runs on this computer."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import columns, llm
from .clean import clean_orders, product_names, tidy_name
from .forecast import tabpfn_forecast
from .note import build_facts, write_note
from .report import render
from .weekly import pick_products, weekly_units


class PipelineError(ValueError):
    """A problem with the input file that the user can fix."""


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, engine="calamine", dtype=str)
        return pd.concat(sheets.values(), ignore_index=True)
    return pd.read_csv(path, dtype="string[pyarrow]", keep_default_na=False, na_values=[""],
                       encoding_errors="replace")


def resolve_columns(raw: pd.DataFrame, use_llm: bool, log) -> tuple[dict, str]:
    headers = [str(h) for h in raw.columns]
    mapping = columns.rule_map(headers)
    how = "header rules"
    if columns.missing_required(mapping) and use_llm and llm.available():
        sample = raw.head(3).astype(str).values.tolist()
        try:
            proposed, info = llm.map_columns(headers, sample)
            mapping = columns.fill_gaps(mapping, proposed, headers)
            how = f"header rules + local model ({info['seconds']} s)"
        except (llm.LLMUnavailable, ValueError) as e:
            log(f"  local model could not map columns: {e}")
    miss = columns.missing_required(mapping)
    if miss:
        raise PipelineError(f"Can't find these columns: {', '.join(miss)}. Headers were: {headers}")
    return mapping, how


def run_pipeline(file: Path, out: Path, as_of: str | None = None, products: int = 20, use_llm: bool = True,
                 label: str = "Your data", log=lambda m: None) -> dict:
    """Clean -> weekly table -> TabPFN-2 forecast -> checked note -> files in ``out``. Returns run.json."""
    t0 = time.time()
    raw = read_table(file)
    log(f"Read {len(raw):,} rows from {file.name}")
    mapping, how = resolve_columns(raw, use_llm, log)
    log(f"Columns found ({how})")
    cr = clean_orders(raw, mapping)
    del raw
    s = cr.stats
    log(f"Cleaned: {s['rows_in']:,} rows in, {s['rows_out']:,} counted as sales "
        f"({s.get('duplicate', 0):,} duplicates, {s.get('cancellation', 0):,} returns, "
        f"{s.get('service_line', 0):,} postage/fee lines set aside)")

    lines = cr.lines
    if as_of:
        as_of_ts = pd.Timestamp(as_of)
        lines = lines[lines["date"] < as_of_ts + pd.Timedelta(days=1)]
    else:
        as_of_ts = lines["date"].max().normalize()
    tab = weekly_units(lines, until=as_of_ts)
    if len(tab) < 12:
        raise PipelineError("Need at least 12 full weeks of orders to forecast.")
    target = tab.index[-1] + pd.Timedelta(days=7)
    tab_ext = pd.concat([tab, pd.DataFrame(0.0, index=[target], columns=tab.columns)])
    tab_ext.index.name = "week"
    prods = pick_products(tab_ext, target, n=products)
    if not prods:
        raise PipelineError("No product sold regularly enough (20 of the last 26 weeks) to forecast.")
    log(f"Forecasting the week of {target:%d %b %Y} for {len(prods)} regular products with TabPFN-2 on this CPU...")
    fc = tabpfn_forecast(tab_ext, prods, target)
    log(f"Forecast done in {fc.seconds:.0f} s ({fc.n_train} training rows)")

    names = product_names(cr.lines)
    facts = build_facts(fc.table, names, target, cr.stats, tab_ext.iloc[:-1])
    log("Writing the note with the local model..." if use_llm else "Writing the note (template)...")
    note = write_note(facts, use_llm=use_llm)
    rejected = sum(1 for at in note.attempts if at.get("ok") is False)
    log(f"Note written by {note.author}" + (f" ({rejected} draft(s) rejected by the number check)" if rejected else ""))

    actuals = None
    full_tab = weekly_units(cr.lines)
    if target in full_tab.index:  # replaying the past: show what really happened
        actuals = {tidy_name(names.get(p, p)): float(full_tab.loc[target, p]) for p in prods}

    out.mkdir(parents=True, exist_ok=True)
    cr.issues.to_csv(out / "issues.csv", index=False)
    cr.lines.to_csv(out / "clean_sales.csv", index=False)
    out_fc = fc.table.assign(name=[tidy_name(names.get(p, p)) for p in fc.table["product"]])
    out_fc.drop(columns=["actual"]).to_csv(out / "forecast.csv", index=False)
    total = time.time() - t0
    run_info = {"forecast time": f"{fc.seconds:.0f} s", "total time": f"{total:.0f} s", "columns": how}
    (out / "report.html").write_text(render(facts, note.text, note.author, cr.stats, label, actuals, run_info))
    run = {
        "file": file.name, "as_of": str(as_of_ts.date()), "target_week": str(target.date()),
        "mapping": mapping, "clean_stats": cr.stats, "facts": facts,
        "note": {"text": note.text, "author": note.author, "attempts": note.attempts},
        "forecast_seconds": round(fc.seconds, 1), "total_seconds": round(total, 1), "actuals": actuals,
    }
    (out / "run.json").write_text(json.dumps(run, indent=2, default=str))
    log(f"Done in {total:.0f} s")
    return run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tidy-predict", description=__doc__,
                                 epilog="Web page instead: tidy-predict serve [--port 8765] [--no-llm]")
    sv = argparse.ArgumentParser(prog="tidy-predict serve", description="open the local web page (127.0.0.1 only)")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--no-llm", action="store_true")
    ap.add_argument("file", type=Path, help="order export (.csv or .xlsx)")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--as-of", help="pretend today is this date (YYYY-MM-DD); forecast the next full week")
    ap.add_argument("--products", type=int, default=20)
    ap.add_argument("--no-llm", action="store_true", help="skip the local model; template note")
    ap.add_argument("--label", default="Your data", help="label shown on the report (e.g. demo data source)")
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        a = sv.parse_args(argv[1:])
        from .web import serve
        serve(a.port, use_llm=not a.no_llm)
        return 0
    a = ap.parse_args(argv)
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    try:
        run = run_pipeline(a.file, a.out, a.as_of, a.products, not a.no_llm, a.label, log)
    except PipelineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(run["note"]["text"])
    log(f"Wrote {a.out}/report.html, forecast.csv, clean_sales.csv, issues.csv, run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
