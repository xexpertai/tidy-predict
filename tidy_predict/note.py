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
    for r in fc.itertuples():
        past = history.loc[history.index < week, r.product]
        last4 = float(past.tail(4).mean())
        med = int(round(r.p50))
        items.append({
            "product": tidy_name(names.get(r.product, r.product)),
            "expected_units": med,
            "low_units": int(round(r.p10)),
            "stock_for_busy_week": int(round(r.p90)),
            "last_week_units": int(round(float(past.iloc[-1]))),
            "avg_last_4_weeks": int(round(last4)),
            "change_vs_4wk_avg_pct": int(round((med - last4) / last4 * 100)) if last4 > 0 else None,
        })
    items.sort(key=lambda d: d["stock_for_busy_week"], reverse=True)
    moves = [d for d in items if d["change_vs_4wk_avg_pct"] is not None]
    rise = max(moves, key=lambda d: d["change_vs_4wk_avg_pct"], default=None)
    drop = min(moves, key=lambda d: d["change_vs_4wk_avg_pct"], default=None)
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
        "items": items,
    }


SYSTEM = ("You write a short weekly restock note for the owner of a small online gift shop. "
          "Use plain, friendly English. Only use numbers that appear in the facts, written exactly as "
          "they appear there. Do not calculate new numbers, do not add totals, do not mention money.")


def _prompt(facts: dict) -> str:
    top = facts["items"][:8]
    return (
        "Facts (JSON):\n" + json.dumps({**facts, "items": top}, ensure_ascii=False) + "\n\n"
        "Write 4 to 6 sentences:\n"
        "1. Which 3 products to have the most stock of this week (the first 3 items), with their "
        "stock_for_busy_week number as units to have ready.\n"
        "2. The biggest expected rise (biggest_rise) and the biggest expected drop (biggest_drop) compared with "
        "the 4-week average, written like 'up 30%' or 'down 42%'.\n"
        "3. One sentence saying how many rows of the file were set aside during cleaning.\n"
        "Never write the JSON field names. No headings, no bullet points, no greeting, no sign-off."
    )


def template_note(facts: dict) -> str:
    it = facts["items"]
    top = ", ".join(f"{d['product']} ({d['stock_for_busy_week']})" for d in it[:3])
    s = [f"For the week starting {facts['week_starting']}, keep the most stock of {top}: these are the "
         "units that would cover a busy week."]
    if facts.get("biggest_rise"):
        r = facts["biggest_rise"]
        s.append(f"The biggest expected rise is {r['product']}, up {r['up_pct']}% on its 4-week average.")
    if facts.get("biggest_drop"):
        d = facts["biggest_drop"]
        s.append(f"The biggest expected drop is {d['product']}, down {d['down_pct']}% on its 4-week average.")
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
