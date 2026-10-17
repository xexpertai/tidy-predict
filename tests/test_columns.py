from tidy_predict import columns


def test_rule_map_online_retail_headers():
    h = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
    m = columns.rule_map(h)
    assert m == {"invoice": "Invoice", "stock_code": "StockCode", "description": "Description",
                 "quantity": "Quantity", "invoice_date": "InvoiceDate", "price": "Price",
                 "customer_id": "Customer ID", "country": "Country"}
    assert columns.missing_required(m) == []


def test_rule_map_other_shop_headers():
    m = columns.rule_map(["Order No", "SKU", "Item name", "Qty", "Order date", "Unit price"])
    assert m["quantity"] == "Qty" and m["invoice_date"] == "Order date" and m["stock_code"] == "SKU"
    assert m["price"] == "Unit price" and m["invoice"] == "Order No"


def test_missing_required_reported():
    m = columns.rule_map(["Bill", "Thing", "How many", "When"])
    assert set(columns.missing_required(m)) >= {"quantity", "invoice_date"}


def test_validate_mapping_rejects_invented_headers_and_reuse():
    h = ["A", "B"]
    got = columns.validate_mapping({"quantity": "A", "price": "A", "invoice_date": "Z", "bogus": "B"}, h)
    assert got == {"quantity": "A"}


def test_model_only_fills_required_gaps():
    h = ["Bill No", "Maal", "Kitne", "Tarikh", "Rate"]
    rule = columns.rule_map(h)                       # invoice + price from rules
    proposed = {"invoice_date": "Tarikh", "quantity": "Kitne", "product": "Maal"}
    m = columns.fill_gaps(rule, proposed, h)
    assert m == {"invoice": "Bill No", "price": "Rate", "invoice_date": "Tarikh", "quantity": "Kitne",
                 "description": "Maal"}


def test_model_cannot_override_rules_reuse_headers_or_invent():
    h = ["Order No", "SKU", "Qty", "When"]
    rule = columns.rule_map(h)
    proposed = {"invoice_date": "Order No", "quantity": "Units", "product": "SKU"}
    m = columns.fill_gaps(rule, proposed, h)
    assert m == rule                                  # reused / invented headers ignored, product already known


def test_model_may_name_products_when_rules_only_found_the_code():
    h = ["Bill No", "Item Code", "Maal", "Kitne", "Tarikh", "Rate"]
    rule = columns.rule_map(h)                       # invoice, stock_code, price from rules
    assert "description" not in rule
    m = columns.fill_gaps(rule, {"invoice_date": "Tarikh", "quantity": "Kitne", "product": "Maal"}, h)
    assert m["stock_code"] == "Item Code" and m["description"] == "Maal"
    assert m["invoice_date"] == "Tarikh" and m["quantity"] == "Kitne"
