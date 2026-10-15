"""Map a client's own column headers onto the fields tidy-predict needs.

Every shop exports orders differently ("Qty", "Units", "Quantity sold"...). The rule-based
matcher below handles common names. If it can't place a required field, the local model can
be asked (see ``llm.map_columns``). Its answer is restricted to the real headers by a JSON schema,
and it is checked again here.
"""
from __future__ import annotations

import re

# canonical field -> header words that usually mean it (lower-case, punctuation stripped)
FIELDS: dict[str, list[str]] = {
    "invoice": ["invoice", "invoiceno", "invoice no", "order", "order id", "order no", "order number", "bill no", "receipt"],
    "stock_code": ["stockcode", "stock code", "sku", "item code", "product code", "code", "article"],
    "description": ["description", "item", "product", "product name", "item name", "name"],
    "quantity": ["quantity", "qty", "units", "unit sold", "units sold", "quantity sold", "count", "pcs"],
    "invoice_date": ["invoicedate", "invoice date", "date", "order date", "sold on", "timestamp", "datetime"],
    "price": ["price", "unit price", "unitprice", "rate", "price each", "mrp"],
    "customer_id": ["customer id", "customerid", "customer", "client", "buyer", "customer no"],
    "country": ["country", "region", "market"],
}
REQUIRED = ("invoice_date", "quantity")
ONE_OF = ("stock_code", "description")  # need at least one to know *what* sold


def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(h).lower()).strip()


def _squash(h: str) -> str:
    return _norm(h).replace(" ", "")


def rule_map(headers: list[str]) -> dict[str, str]:
    """Return {field: header} for the fields we can place with confidence."""
    out: dict[str, str] = {}
    used: set[str] = set()
    # exact (squashed) matches first, then "header contains synonym"
    for strict in (True, False):
        for field, syns in FIELDS.items():
            if field in out:
                continue
            for h in headers:
                if h in used:
                    continue
                hn, hs = _norm(h), _squash(h)
                hit = any(hs == s.replace(" ", "") for s in syns) if strict else any(
                    re.search(rf"\b{re.escape(s)}\b", hn) for s in syns
                )
                if hit:
                    out[field] = h
                    used.add(h)
                    break
    return out


def missing_required(mapping: dict[str, str]) -> list[str]:
    miss = [f for f in REQUIRED if f not in mapping]
    if not any(f in mapping for f in ONE_OF):
        miss.append("stock_code|description")
    return miss


def validate_mapping(mapping: dict, headers: list[str]) -> dict[str, str]:
    """Keep only entries that name a known field and a real, not-yet-used header."""
    clean: dict[str, str] = {}
    used: set[str] = set()
    for field, h in mapping.items():
        if field in FIELDS and isinstance(h, str) and h in headers and h not in used:
            clean[field] = h
            used.add(h)
    return clean


def fill_gaps(rule: dict[str, str], proposed: dict, headers: list[str]) -> dict[str, str]:
    """Policy for the model's answer: it may only fill REQUIRED gaps the header rules left, never
    override a rule match, never reuse a header, and its product column is used as the product name."""
    out = dict(rule)
    used = set(out.values())
    for f in ("invoice_date", "quantity", "product"):
        h = proposed.get(f)
        if not isinstance(h, str) or h not in headers or h in used:
            continue
        if f == "product":
            if any(k in out for k in ONE_OF):
                continue
            out["description"] = h
        elif f not in out:
            out[f] = h
        else:
            continue
        used.add(h)
    return out
