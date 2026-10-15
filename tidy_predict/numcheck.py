"""Deterministic guard: every number in model-written text must come from the computed facts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUM = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*%?")


def _variants(x: float) -> set[str]:
    out: set[str] = set()
    for v in (x, x * 100 if abs(x) <= 1 else None):
        if v is None:
            continue
        for d in (0, 1, 2, 3):
            r = round(v, d)
            s = f"{r:.{d}f}"
            out.add(s)
            if "." in s:
                out.add(s.rstrip("0").rstrip("."))
    return out


def _norm(token: str) -> str:
    t = token.replace(",", "").replace("%", "").strip().lstrip("+")
    if t.startswith("-") and float(t) == 0:
        t = t[1:]
    if "." in t:
        t = t.rstrip("0").rstrip(".") or "0"
    return t


@dataclass
class CheckResult:
    ok: bool
    found: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


def allowed_numbers(facts) -> set[str]:
    allowed: set[str] = set()

    def walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            # "down 18%" is a fair way to write -18, so the magnitude is allowed too
            for x in {float(o), abs(float(o))}:
                allowed.update(_norm(v) for v in _variants(x))
        elif isinstance(o, str):
            for m in _NUM.finditer(o):
                allowed.add(_norm(m.group()))
                allowed.add(_norm(m.group()).lstrip("-"))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(facts)
    return allowed


def check(text: str, facts) -> CheckResult:
    allowed = allowed_numbers(facts)
    found = [m.group().strip() for m in _NUM.finditer(text)]
    unknown = [f for f in found if _norm(f) not in allowed]
    return CheckResult(ok=not unknown, found=found, unknown=unknown)
