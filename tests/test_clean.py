import pandas as pd

from tidy_predict.clean import clean_orders, tidy_name
from tidy_predict.columns import rule_map

ROWS = [
    # Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID
    ["1001", "85123A", "HEART HOLDER", "6", "2011-01-03 10:00", "2.55", "17850"],
    ["1001", "85123A", "HEART HOLDER", "6", "2011-01-03 10:00", "2.55", "17850"],   # exact duplicate
    ["1002", "22423", "CAKE  STAND ", "2", "04/01/2011 11:30", "12.75", "13047"],   # day-first date, spaces
    ["1003", "POST", "POSTAGE", "1", "2011-01-04", "18", "12583"],                 # service line
    ["1004", "22423", "CAKE STAND", "3", "2011-01-05", "12.75", "13047"],          # undone by C1005
    ["C1005", "22423", "CAKE STAND", "-3", "2011-01-06", "12.75", "13047"],        # cancellation
    ["1006", "21730", "LANTERN", "abc", "2011-01-06", "4.25", "17850"],            # bad quantity
    ["1007", "21730", "LANTERN", "4", "not a date", "4.25", "17850"],              # bad date
    ["1008", "21730", "LANTERN", "10", "2011-01-07", "0", "17850"],                # zero price
    ["1009", "21730", "LANTERN", "1,200", "2011-01-07", "4.25", "17850"],          # thousands separator
]
HEAD = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID"]


def run():
    raw = pd.DataFrame(ROWS, columns=HEAD)
    return clean_orders(raw, rule_map(HEAD))


def test_counts_and_reasons():
    r = run()
    s = r.stats
    assert s["rows_in"] == 10
    assert s["duplicate"] == 1 and s["service_line"] == 1 and s["cancellation"] == 1
    assert s["cancelled_sale"] == 1 and s["bad_quantity"] == 1 and s["bad_date"] == 1 and s["zero_price"] == 1
    assert s["rows_out"] == 3
    # every set-aside row is listed with its sheet row number
    assert len(r.issues) == s["rows_in"] - s["rows_out"]
    assert sorted(r.issues["source_row"]) == [3, 5, 6, 7, 8, 9, 10]


def test_values_are_normalised():
    lines = run().lines.set_index("source_row")
    assert lines.loc[4, "description"] == "CAKE STAND"
    assert lines.loc[4, "date"] == pd.Timestamp("2011-01-04 11:30")
    assert lines.loc[11, "quantity"] == 1200


def test_unmatched_cancellation_does_not_remove_a_sale():
    raw = pd.DataFrame([["1", "111", "X", "5", "2011-01-03", "1", "9"],
                        ["C2", "111", "X", "-4", "2011-01-04", "1", "9"]], columns=HEAD)
    r = clean_orders(raw, rule_map(HEAD))
    assert r.stats["rows_out"] == 1 and r.stats["cancelled_sale"] == 0


def test_tidy_name():
    assert tidy_name("WHITE  HANGING HEART T-LIGHT HOLDER") == "White hanging heart t-light holder"
