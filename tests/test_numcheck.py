from tidy_predict.numcheck import check

FACTS = {"rows_set_aside": 1234, "items": [{"product": "Pack of 72 cake cases", "stock_for_busy_week": 310,
                                            "change_vs_4wk_avg_pct": -18}]}


def test_accepts_numbers_from_facts_including_names_and_commas():
    assert check("Stock 310 of the Pack of 72 cake cases; 1,234 rows were set aside.", FACTS).ok


def test_rejects_invented_numbers():
    r = check("Stock 350 units, about 20% more than usual.", FACTS)
    assert not r.ok and r.unknown == ["350", "20%"]


def test_percent_and_sign():
    assert check("It is down 18% (-18).", FACTS).ok
