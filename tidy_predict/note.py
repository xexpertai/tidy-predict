"""The weekly restock note: a few plain sentences a shop owner can act on.

A local model (Gemma via llama.cpp) writes it from a small facts table. Then ``numcheck`` pulls
every number out of the text and rejects the note if any number isn't in the facts. One retry
(told which numbers were wrong), then a plain template. The note always says who wrote it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from . import llm
from .clean import tidy_name
from .forecast import QCOLS, chance_demand_above
from .numcheck import check


@dataclass
class Note:
    text: str
    author: str                      # "gemma-4-E2B-it-Q4_0 (local)" or "template"
    attempts: list[dict] = field(default_factory=list)


def build_facts(fc: pd.DataFrame, names: dict[str, str], week: pd.Timestamp, clean_stats: dict,
                history: pd.DataFrame) -> dict:
    """``fc``: product, p10, p50, p90. ``history``: weekly units table (rows = weeks)."""
    items = []
    has_grid = all(c in fc.columns for c in QCOLS)
    for r in fc.itertuples():
        past = history.loc[history.index < week, r.product]
        last4 = float(past.tail(4).mean())
        busiest4 = float(past.tail(4).max())
        med = int(round(r.p50))
        # chance the week's demand is above what the shop would have if it stocks the busiest of its last 4 weeks
        # (reference picked on validation weeks, eval/sellout_recalibrate.py)
        sell_out = (int(round(100 * chance_demand_above(r._asdict(), busiest4))) if has_grid else None)
        last_wk = float(past.iloc[-1])
        wide = r.p90 / max(r.p10, 1.0) > WIDE_RATIO
        far_below = last4 > 0 and last_wk < FAR_BELOW * last4
        items.append({
            "product": tidy_name(names.get(r.product, r.product)),
            "expected_units": med,
            "low_units": int(round(r.p10)),
            "stock_for_busy_week": int(round(r.p90)),
            "last_week_units": int(round(last_wk)),
            "busiest_of_last_4_weeks": int(round(busiest4)),
            "check_by_hand": bool(wide or far_below),
            "avg_last_4_weeks": int(round(last4)),
            "change_vs_4wk_avg_pct": int(round((med - last4) / last4 * 100)) if last4 > 0 else None,
            "sell_out_chance_pct": sell_out,
        })
    items.sort(key=lambda d: d["stock_for_busy_week"], reverse=True)
    # advice is built only from products whose range is trustworthy; the others are listed to check by hand
    ok_items = [d for d in items if not d["check_by_hand"]]
    check_names = [d["product"] for d in items if d["check_by_hand"]]
    moves = [d for d in ok_items if d["change_vs_4wk_avg_pct"] is not None]
    rise = max(moves, key=lambda d: d["change_vs_4wk_avg_pct"], default=None)
    drop = min(moves, key=lambda d: d["change_vs_4wk_avg_pct"], default=None)
    risky = sorted((d for d in ok_items if d["sell_out_chance_pct"] is not None),
                   key=lambda d: d["sell_out_chance_pct"], reverse=True)[:2]
    return {
        "week_starting": week.strftime("%d %b %Y"),
        "products_forecast": len(items),
        "average_window_weeks": 4,
        "rows_in_file": clean_stats.get("rows_in"),
        "rows_used_as_sales": clean_stats.get("rows_out"),
        "rows_set_aside": clean_stats.get("rows_in", 0) - clean_stats.get("rows_out", 0),
        "biggest_rise": ({"product": rise["product"], "up_pct": rise["change_vs_4wk_avg_pct"]}
                         if rise and rise["change_vs_4wk_avg_pct"] > 0 else None),
        "biggest_drop": ({"product": drop["product"], "down_pct": -drop["change_vs_4wk_avg_pct"]}
                         if drop and drop["change_vs_4wk_avg_pct"] < 0 else None),
        "most_likely_to_sell_out": [{"product": d["product"], "chance_pct": d["sell_out_chance_pct"]} for d in risky],
        "most_stock_to_have_ready": [{"product": d["product"], "units": d["stock_for_busy_week"]} for d in ok_items[:3]],
        "check_by_hand": [{"product": n} for n in check_names[:3]],
        "items": items,
    }


WIDE_RATIO = 10.0   # P90 / P10 above this: the range is too wide to order from
FAR_BELOW = 0.25    # last week under a quarter of the 4-week average: the history is unreliable

SYSTEM = ("You write a short weekly restock note for the owner of a small online gift shop. "
          "Use plain, friendly English. Only use numbers that appear in the facts, written exactly as "
          "they appear there. Do not calculate new numbers, do not add totals, do not mention money.")


def _prompt(facts: dict) -> str:
    top = facts["items"][:8]
    return (
        "Facts (JSON):\n" + json.dumps({**facts, "items": top}, ensure_ascii=False) + "\n\n"
        "Write 5 to 7 sentences:\n"
        "1. Which 3 products to have the most stock of this week (most_stock_to_have_ready), with their "
        "units number as units to have ready.\n"
        "2. The biggest expected rise (biggest_rise) and the biggest expected drop (biggest_drop) compared with "
        "the 4-week average, written like 'up 30%' or 'down 42%'.\n"
        "3. If most_likely_to_sell_out is not empty: one sentence naming those products and their chance_pct of "
        "selling out if the shop only stocks the busiest of its last 4 weeks, written like 'a 62% chance'.\n"
        "4. If check_by_hand is not empty: one sentence naming those products and saying their forecast range is "
        "very wide or last week was far below normal, so check them by hand and do not order from the forecast. "
        "Give no stock number for them.\n"
        "5. One sentence saying how many rows of the file were set aside during cleaning.\n"
        "Never write the JSON field names. No headings, no bullet points, no greeting, no sign-off."
    )


def template_note(facts: dict) -> str:
    it = facts["items"]
    top = ", ".join(f"{d['product']} ({d['units']})" for d in facts["most_stock_to_have_ready"])
    s = [f"For the week starting {facts['week_starting']}, keep the most stock of {top}: these are the "
         "units that would cover a busy week."]
    if facts.get("biggest_rise"):
        r = facts["biggest_rise"]
        s.append(f"The biggest expected rise is {r['product']}, up {r['up_pct']}% on its 4-week average.")
    if facts.get("biggest_drop"):
        d = facts["biggest_drop"]
        s.append(f"The biggest expected drop is {d['product']}, down {d['down_pct']}% on its 4-week average.")
    risk = facts.get("most_likely_to_sell_out") or []
    if risk:
        parts = " and ".join(f"{d['product']} ({d['chance_pct']}% chance)" for d in risk)
        s.append(f"If you only stock the busiest of your last 4 weeks, the products most likely to sell out are {parts}.")
    if facts.get("check_by_hand"):
        names = " and ".join(d["product"] for d in facts["check_by_hand"])
        s.append(f"Wide range, check by hand: {names}. Their range is very wide or last week was far below normal, so do not order them from this forecast.")
    s.append(f"{facts['rows_set_aside']} of {facts['rows_in_file']} rows in the file were set aside while "
             "cleaning (duplicates, returns, postage and similar); see the issues list.")
    return " ".join(s)


def write_note(facts: dict, use_llm: bool = True, url: str = llm.DEFAULT_URL) -> Note:
    attempts: list[dict] = []
    if use_llm and llm.available(url):
        author = f"{llm.model_name(url)} (local, llama.cpp)"
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _prompt(facts)}]
        for attempt in range(2):
            try:
                text, info = llm.chat(msgs, url=url, max_tokens=320)
            except llm.LLMUnavailable as e:
                attempts.append({"error": str(e)})
                break
            text = " ".join(text.split())
            res = check(text, facts)
            attempts.append({"text": text, "ok": res.ok, "unknown_numbers": res.unknown, **info})
            if res.ok and text:
                return Note(text=text, author=author, attempts=attempts)
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "These numbers are not in the facts: "
                      + ", ".join(res.unknown) + ". Rewrite the note using only numbers from the facts."}]
    return Note(text=template_note(facts), author="template", attempts=attempts)
