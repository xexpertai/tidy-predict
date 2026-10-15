import pandas as pd

from tidy_predict import llm, note
from tidy_predict.report import render

FACTS = {"week_starting": "28 Nov 2011", "products_forecast": 2, "average_window_weeks": 4, "rows_in_file": 100, "rows_used_as_sales": 80,
         "rows_set_aside": 20, "biggest_rise": {"product": "Heart holder", "up_pct": 25},
         "biggest_drop": {"product": "Cake stand", "down_pct": 33}, "items": [
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
    fc = pd.DataFrame({"product": ["A", "B", "C"], "p10": [5, 50, 20], "p50": [20, 60, 50], "p90": [30, 900, 80]})
    f = note.build_facts(fc, {}, pd.Timestamp("2011-01-31"), {"rows_in": 10, "rows_out": 8}, hist)
    assert f["biggest_rise"] == {"product": "A", "up_pct": 100}
    assert f["biggest_drop"] == {"product": "B", "down_pct": 40}
    assert [d["product"] for d in f["items"]] == ["B", "C", "A"]   # sorted by busy-week stock
