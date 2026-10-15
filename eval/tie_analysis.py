"""A closer look at "TabPFN-2 ties the 4-week mean" (no model is run; light).

Inputs: eval/results/backtest_predictions.csv (the 12 test weeks, run once), weekly_units.csv.gz and
model_selection.json. Writes eval/results/tie_analysis.json.

1. Week by week: in how many test weeks did TabPFN-2's median beat the 4-week mean? Pooled WAPE without the
   last week (28 Nov 2011).
2. Stocking: if a shop stocks each product to an "upper" number, how often is it in stock, and how many
   units are left over / short?
3. Proper scoring rules for the range: pinball loss at P10 and P90, and the 80% interval (Winkler) score.
4. The missing simple baseline: "4-week mean x k". k is tuned on the VALIDATION weeks only (Jul-Aug 2011,
   the same weeks used for model selection), separately for P10, P50 and P90, then applied unchanged to the
   test weeks. The k tuned on the test weeks themselves is also shown, clearly labelled as an oracle that
   no real user could have.
5. The naive per-product ratio band from interval_baseline.py, for comparison.
Usage: python eval/tie_analysis.py eval/results
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tidy_predict.forecast import wape
from tidy_predict.weekly import pick_products

R = Path(sys.argv[1])
tab = pd.read_csv(R / "weekly_units.csv.gz", index_col=0, parse_dates=True)
pred = pd.read_csv(R / "backtest_predictions.csv", parse_dates=["week"])
sel = json.loads((R / "model_selection.json").read_text())
a = pred["actual"].to_numpy(float)


def pinball(y, q, tau):
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def winkler(y, lo, hi, alpha=0.2):
    w = (hi - lo) + (2 / alpha) * (lo - y) * (y < lo) + (2 / alpha) * (y - hi) * (y > hi)
    return float(np.mean(w))


def stocking(y, stock):
    return {"in_stock_share": round(float(np.mean(y <= stock)), 4),
            "leftover_units": int(round(np.maximum(stock - y, 0).sum())),
            "short_units": int(round(np.maximum(y - stock, 0).sum()))}


# --- 1. week by week -------------------------------------------------------------------------------------------
weeks = sorted(pred["week"].unique())
per_week = []
for wk in weeks:
    g = pred[pred["week"] == wk]
    per_week.append({"week": str(pd.Timestamp(wk).date()), "tabpfn_p50": round(wape(g.actual, g.p50), 4),
                     "mean_4w": round(wape(g.actual, g.mean_4w), 4)})
wins = sum(w["tabpfn_p50"] < w["mean_4w"] for w in per_week)
first11 = pred[pred["week"] < weeks[-1]]
last = pred[pred["week"] == weeks[-1]]

# --- 4. "4-week mean x k", k tuned on validation weeks only --------------------------------------------------------
val_weeks = [pd.Timestamp(w) for w in sel["validation_weeks"]]
vrows = []
for wk in val_weeks:
    i = tab.index.get_loc(wk)
    for p in pick_products(tab, wk, n=20):
        vrows.append((tab[p].iloc[i - 4:i].mean(), tab[p].iloc[i]))
vm, vy = np.array(vrows).T
grid = np.round(np.arange(0.05, 4.001, 0.01), 2)


def best_k(m, y, tau=None):
    if tau is None:  # point forecast: minimise WAPE
        return float(grid[np.argmin([np.abs(y - k * m).sum() for k in grid])])
    return float(grid[np.argmin([pinball(y, k * m, tau) for k in grid])])


k_val = {"p10": best_k(vm, vy, 0.1), "p50": best_k(vm, vy), "p90": best_k(vm, vy, 0.9)}
tm = pred["mean_4w"].to_numpy(float)
k_oracle = {"p10": best_k(tm, a, 0.1), "p50": best_k(tm, a), "p90": best_k(tm, a, 0.9)}

# --- 5. naive per-product ratio band (same rule as interval_baseline.py) ----------------------------------------
lo_n, hi_n = [], []
for r in pred.itertuples():
    y = tab[r.product]
    i = tab.index.get_loc(r.week)
    m4 = y.rolling(4).mean().shift(1)
    ratios = (y / m4).iloc[max(5, i - 52):i].replace([np.inf, -np.inf], np.nan).dropna()
    lo_n.append(m4.iloc[i] * np.quantile(ratios, 0.1))
    hi_n.append(m4.iloc[i] * np.quantile(ratios, 0.9))
lo_n, hi_n = np.array(lo_n), np.array(hi_n)


def band(lo, hi):
    return {"coverage_p10_p90": round(float(np.mean((a >= lo) & (a <= hi))), 4),
            "relative_width": round(float((hi - lo).sum() / a.sum()), 4),
            "pinball_p10": round(pinball(a, lo, 0.1), 1), "pinball_p90": round(pinball(a, hi, 0.9), 1),
            "winkler_80": round(winkler(a, lo, hi), 1), "stock_to_top": stocking(a, hi)}


out = {
    "note": "All on the 12 test weeks x 20 products (240 product-weeks) unless stated. Lower is better for WAPE, "
            "pinball and Winkler. k for '4-week mean x k' was tuned on the 7 validation weeks only.",
    "1_week_by_week": {
        "per_week": per_week, "tabpfn_wins": wins, "mean_4w_wins": len(per_week) - wins,
        "pooled_wape_first_11_weeks": {"tabpfn_p50": round(wape(first11.actual, first11.p50), 4),
                                       "mean_4w": round(wape(first11.actual, first11.mean_4w), 4)},
        "last_week": {"week": per_week[-1]["week"], "tabpfn_p50": per_week[-1]["tabpfn_p50"],
                      "mean_4w": per_week[-1]["mean_4w"]},
        "validation_mean_weekly_wape": {"tabpfn_level (chosen)": round(sel["mean_weekly_wape"]["tabpfn_level"], 4),
                                        "mean_4w": round(sel["mean_weekly_wape"]["mean_4w"], 4)},
    },
    "2_3_ranges_and_stocking": {
        "tabpfn_2": band(pred["p10"].to_numpy(), pred["p90"].to_numpy()),
        "mean_4w_x_k_tuned_on_validation": {"k": k_val, **band(k_val["p10"] * tm, k_val["p90"] * tm)},
        "naive_per_product_ratio_band": band(lo_n, hi_n),
        "ORACLE_mean_4w_x_k_tuned_on_test": {"k": k_oracle, **band(k_oracle["p10"] * tm, k_oracle["p90"] * tm),
                                             "warning": "k chosen on the test weeks themselves; not achievable in practice"},
    },
    "4_point_forecast": {
        "tabpfn_p50_wape": round(wape(a, pred["p50"]), 4), "mean_4w_wape": round(wape(a, tm), 4),
        "mean_4w_x_k_val_wape": round(wape(a, k_val["p50"] * tm), 4),
    },
    "validation_rows": int(len(vy)),
}
# --- demo week (28 Nov 2011) from the recorded web run ----------------------------------------------------------
demo = json.loads((R / "demo_web_run.json").read_text())
items, act = demo["facts"]["items"], demo["actuals"]
names = pd.read_csv(R / "product_names.csv.gz", index_col=0)["description"]
rabbit = [c for c in names.index if "RABBIT NIGHT LIGHT" in str(names[c])][0]
rs = tab[rabbit]
out["demo_week"] = {
    "week": demo["target_week"],
    "inside_p10_p90": sum(i["low_units"] <= act[i["product"]] <= i["stock_for_busy_week"] for i in items),
    "above_p90": [i["product"] for i in items if act[i["product"]] > i["stock_for_busy_week"]],
    "below_p10": [i["product"] for i in items if act[i["product"]] < i["low_units"]],
    "sum_actual": int(sum(act.values())), "sum_expected": int(sum(i["expected_units"] for i in items)),
    "rabbit_night_light": {"expected": next(i for i in items if i["product"] == "Rabbit night light"),
                           "actual": act["Rabbit night light"],
                           "rank_of_that_week_in_its_history": int((rs > rs.loc[demo["target_week"]]).sum() + 1),
                           "best_week": [str(rs.idxmax().date()), float(rs.max())]},
}
(R / "tie_analysis.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "1_week_by_week"}, indent=1)[-900:])
print(json.dumps({k: v for k, v in out["1_week_by_week"].items() if k != "per_week"}, indent=1))
