import numpy as np
import pandas as pd

from tidy_predict.weekly import FEATURES, feature_rows, pick_products, weekly_units


def lines_for(weeks=70):
    start = pd.Timestamp("2010-01-04")  # a Monday
    rows = []
    for w in range(weeks):
        for p, base in (("A", 10), ("B", 3)):
            rows.append({"date": start + pd.Timedelta(days=7 * w + 2), "product": p, "quantity": base + w % 3})
        if w % 4 == 0:
            rows.append({"date": start + pd.Timedelta(days=7 * w + 1), "product": "RARE", "quantity": 1})
    return pd.DataFrame(rows)


def test_weekly_units_drops_partial_last_week():
    l = lines_for(10)
    full = weekly_units(l, until=pd.Timestamp("2010-03-14"))      # Sunday: week 10 complete
    part = weekly_units(l, until=pd.Timestamp("2010-03-10"))      # Wednesday: week 10 partial
    assert len(full) == 10 and len(part) == 9
    assert full.index[0].weekday() == 0


def test_pick_products_prefers_regular_sellers():
    tab = weekly_units(lines_for())
    assert pick_products(tab, tab.index[-1], n=5) == ["A", "B"]


def test_features_use_only_the_past():
    tab = weekly_units(lines_for())
    target = tab.index[60]
    f = feature_rows(tab, ["A"], [target]).iloc[0]
    assert np.isclose(f["lag1"], np.log1p(tab.loc[tab.index[59], "A"]))
    assert np.isclose(f["lag52"], np.log1p(tab.loc[tab.index[8], "A"]))
    assert np.isclose(f["target"], np.log1p(tab.loc[target, "A"]))
    # changing the target week's value must not change any feature
    tab2 = tab.copy(); tab2.loc[target, "A"] = 999
    f2 = feature_rows(tab2, ["A"], [target]).iloc[0]
    assert all(np.isclose(f[c], f2[c], equal_nan=True) for c in FEATURES)
