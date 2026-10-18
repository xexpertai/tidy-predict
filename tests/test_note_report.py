import pandas as pd

from tidy_predict import llm, note
from tidy_predict.note import build_facts
from tidy_predict.report import render

FACTS = {"week_starting": "28 Nov 2011", "products_forecast": 2, "average_window_weeks": 4, "rows_in_file": 100, "rows_used_as_sales": 80,
         "rows_set_aside": 20, "biggest_rise": {"product": "Heart holder", "up_pct": 25},
         "biggest_drop": {"product": "Cake stand", "down_pct": 33},
         "most_stock_to_have_ready": [{"product": "Heart holder", "units": 800}, {"product": "Cake stand", "units": 70}],
         "check_by_hand": [], "items": [
             {"product": "Heart holder", "expected_units": 500, "low_units": 300, "stock_for_busy_week": 800,
              "last_week_units": 450, "avg_last_4_weeks": 400, "change_vs_4wk_avg_pct": 25},
             {"product": "Cake stand", "expected_units": 40, "low_units": 20, "stock_for_busy_week": 70,
              "last_week_units": 50, "avg_last_4_weeks": 60, "change_vs_4wk_avg_pct": -33}]}


def test_template_note_passes_its_own_check():
    from tidy_predict.numcheck import check
    t = note.template_note(FACTS)
    assert check(t, FACTS).ok and "Heart holder (800)" in t


def test_bad_model_note_is_retried_then_replaced(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "available", lambda url=None: True)
    monkeypatch.setattr(llm, "model_name", lambda url=None: "gemma-test")

    def fake_chat(msgs, **kw):
        calls.append(msgs)
        return "Order 999 heart holders.", {"seconds": 0.1}
    monkeypatch.setattr(llm, "chat", fake_chat)
    n = note.write_note(FACTS)
    assert n.author == "template" and len(calls) == 2
    assert "999" in calls[1][-1]["content"]          # the retry names the bad number
    assert [a["ok"] for a in n.attempts] == [False, False]


def test_good_model_note_is_kept(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda url=None: True)
    monkeypatch.setattr(llm, "model_name", lambda url=None: "gemma-test")
    monkeypatch.setattr(llm, "chat", lambda msgs, **kw: ("Keep 800 heart holders ready; cake stands are down 33%.", {}))
    n = note.write_note(FACTS)
    assert n.author.startswith("gemma-test") and "800" in n.text


def test_no_server_means_template(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda url=None: False)
    assert note.write_note(FACTS).author == "template"


def test_report_has_attribution_and_escapes():
    f = {**FACTS, "items": [{**FACTS["items"][0], "product": "<script>x</script>"}]}
    h = render(f, "note & more", "template", {"rows_in": 100, "rows_out": 80, "duplicate": 5}, "Demo data")
    assert "Built with PriorLabs-TabPFN" in h
    assert "<script>x" not in h and "note &amp; more" in h
    assert "exact duplicate of an earlier row" in h


def test_build_facts_finds_biggest_moves_over_all_items():
    hist = pd.DataFrame({"A": [10, 10, 10, 10], "B": [100, 100, 100, 100], "C": [50, 50, 50, 50]},
                        index=pd.date_range("2011-01-03", periods=4, freq="W-MON"))
    fc = pd.DataFrame({"product": ["A", "B", "C"], "p10": [5, 50, 20], "p50": [20, 60, 50], "p90": [30, 400, 80]})
    f = note.build_facts(fc, {}, pd.Timestamp("2011-01-31"), {"rows_in": 10, "rows_out": 8}, hist)
    assert f["biggest_rise"] == {"product": "A", "up_pct": 100}
    assert f["biggest_drop"] == {"product": "B", "down_pct": 40}
    assert [d["product"] for d in f["items"]] == ["B", "C", "A"]   # sorted by busy-week stock


def test_chance_demand_above_from_quantile_grid():
    from tidy_predict.forecast import QCOLS, QUANTILES, chance_demand_above
    row = {c: 100.0 + 10 * i for i, c in enumerate(QCOLS)}      # 100..280, P5..P95
    assert chance_demand_above(row, 50) == 0.95                  # below every quantile: capped
    assert chance_demand_above(row, 1000) == 0.05                # above every quantile: floored
    p_mid = chance_demand_above(row, row["p50"])
    assert abs(p_mid - 0.5) < 1e-9
    assert chance_demand_above(row, 120) > chance_demand_above(row, 200)   # more stock, less risk
    assert len(QUANTILES) == 19


def test_facts_carry_sell_out_chance():
    from tidy_predict.forecast import QCOLS
    hist = pd.DataFrame({"A": [10.0] * 8}, index=pd.date_range("2011-01-03", periods=8, freq="W-MON"))
    fc = pd.DataFrame({"product": ["A"], **{c: [5.0 + 3 * i] for i, c in enumerate(QCOLS)}})
    facts = build_facts(fc, {"A": "WIDGET"}, pd.Timestamp("2011-03-07"), {"rows_in": 1, "rows_out": 1}, hist)
    assert facts["items"][0]["sell_out_chance_pct"] is not None
    assert facts["most_likely_to_sell_out"][0]["chance_pct"] == facts["items"][0]["sell_out_chance_pct"]


def test_wide_range_item_is_flagged_and_kept_out_of_advice():
    hist = pd.DataFrame({"A": [900, 900, 900, 22], "B": [100] * 4},
                        index=pd.date_range("2011-01-03", periods=4, freq="W-MON"))
    fc = pd.DataFrame({"product": ["A", "B"], "p10": [44, 50], "p50": [500, 100], "p90": [3000, 150]})
    f = build_facts(fc, {}, pd.Timestamp("2011-01-31"), {"rows_in": 10, "rows_out": 8}, hist)
    flags = {d["product"]: d["check_by_hand"] for d in f["items"]}
    assert flags == {"A": True, "B": False}
    assert [d["product"] for d in f["most_stock_to_have_ready"]] == ["B"]
    assert f["check_by_hand"] == [{"product": "A"}]
    t = note.template_note(f)
    assert "check by hand" in t.lower() and "3000" not in t and "3,000" not in t
