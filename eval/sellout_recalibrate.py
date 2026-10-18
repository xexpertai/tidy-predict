"""Gap-2 follow-up: can the chance of selling out be recalibrated honestly?

Chronological split of the 12 backtest weeks (240 product-weeks), fixed BEFORE looking at any result:
  fit  = weeks 1-6   (calibrators are fitted here)
  val  = weeks 7-9   (the method is chosen here, by Brier, and only here)
  test = weeks 10-12 (touched once; the chosen method is refitted on weeks 1-9 and scored here)
Candidates: stock reference (4-week mean, 4-week max) x calibration (none, Platt, isotonic).
Baseline: always say the base rate seen in the fitting weeks.
Usage: python eval/sellout_recalibrate.py eval/results  -> eval/results/sellout_recalibrated.json
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from tidy_predict.forecast import chance_demand_above

res = Path(sys.argv[1])
d = pd.read_csv(res / "backtest_v2.csv", parse_dates=["week"])
tab = pd.read_csv(res / "weekly_units.csv.gz", index_col=0, parse_dates=True)
d["max_4w"] = [tab.loc[tab.index < r.week, str(r.product)].tail(4).max() if str(r.product) in tab.columns else np.nan
               for r in d.itertuples()]
if d["max_4w"].isna().any():
    tab.columns = tab.columns.astype(str); d["product"] = d["product"].astype(str)
    d["max_4w"] = [tab.loc[tab.index < r.week, r.product].tail(4).max() for r in d.itertuples()]
weeks = sorted(d.week.unique())
assert len(weeks) == 12
fit_w, val_w, test_w = weeks[:6], weeks[6:9], weeks[9:]
refs = {"4-week mean": "mean_4w", "4-week max": "max_4w"}
brier = lambda p, y: float(((p - y) ** 2).mean())
logit = lambda p: np.log(np.clip(p, .02, .98) / (1 - np.clip(p, .02, .98)))

def fit_cal(kind, p, y):
    if kind == "none": return lambda q: q
    if kind == "platt":
        m = LogisticRegression(C=1e6).fit(logit(p).reshape(-1, 1), y)
        return lambda q: m.predict_proba(logit(q).reshape(-1, 1))[:, 1]
    m = IsotonicRegression(y_min=0.02, y_max=0.98, out_of_bounds="clip").fit(p, y)
    return m.predict

def prep(ref):
    p = np.array([chance_demand_above(r, r[ref]) for _, r in d.iterrows()])
    y = (d["actual"] > d[ref]).astype(float).to_numpy()
    return p, y

mask = lambda ws: d.week.isin(ws).to_numpy()
out = {"split": {"fit_weeks": [str(w.date()) for w in fit_w], "val_weeks": [str(w.date()) for w in val_w],
                 "test_weeks": [str(w.date()) for w in test_w]}, "validation": [], "test": {}}
best = None
for rname, ref in refs.items():
    p, y = prep(ref)
    f, v = mask(fit_w), mask(val_w)
    base = y[f].mean()
    out["validation"].append({"stock_reference": rname, "calibration": "constant (base rate of fit weeks)", "brier": round(brier(base, y[v]), 4)})
    for kind in ("none", "platt", "isotonic"):
        c = fit_cal(kind, p[f], y[f])
        b = brier(c(p[v]), y[v])
        out["validation"].append({"stock_reference": rname, "calibration": kind, "brier": round(b, 4)})
        if best is None or b < best[0]: best = (b, rname, ref, kind)
b, rname, ref, kind = best
out["chosen_on_validation"] = {"stock_reference": rname, "calibration": kind, "val_brier": round(b, 4)}
p, y = prep(ref)
tr, te = mask(fit_w + val_w), mask(test_w)
c = fit_cal(kind, p[tr], y[tr])
pt, yt = c(p[te]), y[te]
base = y[tr].mean()
raw_te = p[te]
# the original headline definition (4-week mean) on the same test weeks, uncalibrated, for reference
p0, y0 = prep("mean_4w")
out["test"] = {
    "n": int(te.sum()), "share_really_above": round(float(yt.mean()), 3),
    "brier_chosen_method": round(brier(pt, yt), 4),
    "brier_constant_base_rate": round(brier(base, yt), 4),
    "brier_uncalibrated_same_reference": round(brier(raw_te, yt), 4),
    "brier_original_4wk_mean_uncalibrated": round(brier(p0[te], y0[te]), 4),
    "beats_constant": bool(brier(pt, yt) < brier(base, yt)),
    "auc_ranking_chosen": round(float(roc_auc_score(yt, pt)), 3),
    "auc_ranking_original_raw_all_240": round(float(roc_auc_score(y0, p0)), 3),
}
# reliability on test
bins = [(0, .3), (.3, .5), (.5, 1.01)]
out["test"]["reliability"] = [{"predicted_range": f"{int(lo*100)}-{min(int(hi*100),100)}%", "n": int(((pt >= lo) & (pt < hi)).sum()),
    "mean_predicted_pct": round(float(pt[(pt >= lo) & (pt < hi)].mean() * 100), 1) if ((pt >= lo) & (pt < hi)).any() else None,
    "really_above_pct": round(float(yt[(pt >= lo) & (pt < hi)].mean() * 100), 1) if ((pt >= lo) & (pt < hi)).any() else None} for lo, hi in bins]
# ranking signal on all 240 (no fitting involved): top vs bottom third of the raw 4-week-mean chance
r = pd.Series(p0).rank(pct=True)
out["ranking_all_240_raw"] = {"top_third_really_above_pct": round(float(y0[r > 2/3].mean() * 100), 1),
                              "bottom_third_really_above_pct": round(float(y0[r <= 1/3].mean() * 100), 1),
                              "auc": round(float(roc_auc_score(y0, p0)), 3)}
pm, ym = prep("max_4w")
out["all_240_uncalibrated_4wk_max"] = {"share_really_above": round(float(ym.mean()), 3), "brier": round(brier(pm, ym), 4),
    "brier_constant_base_rate": round(brier(ym.mean(), ym), 4), "auc": round(float(roc_auc_score(ym, pm)), 3),
    "note": "no fitting involved, but the reference was picked on weeks 7-9, so read the test block as the headline"}
rm = pd.Series(pm).rank(pct=True)
out["all_240_uncalibrated_4wk_max"].update(top_third_really_above_pct=round(float(ym[rm > 2/3].mean() * 100), 1),
                                           bottom_third_really_above_pct=round(float(ym[rm <= 1/3].mean() * 100), 1))
(res / "sellout_recalibrated.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
