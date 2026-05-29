"""
NAV universe filter: Equity + Hybrid + Liquid only.

Liquid includes:
  - SEBI category ``Debt Scheme - Liquid Fund``
  - Noisy category label ``Liquid`` (case-insensitive)
  - Scheme name contains the word ``liquid`` when category is not Equity/Hybrid
    (captures liquid funds mis-tagged under Income, Direct, etc.)
"""
from __future__ import annotations

import re

_LIQUID_WORD = re.compile(r"\bliquid\b", re.IGNORECASE)


def is_equity_or_hybrid(scheme_category: str | None) -> bool:
    cat = (scheme_category or "").strip()
    return cat.startswith("Equity Scheme") or cat.startswith("Hybrid Scheme")


def is_liquid_fund(scheme_category: str | None, scheme_name_raw: str | None) -> bool:
    if is_equity_or_hybrid(scheme_category):
        return False
    cat = (scheme_category or "").strip()
    if cat == "Debt Scheme - Liquid Fund":
        return True
    if cat.lower() == "liquid":
        return True
    name = (scheme_name_raw or "").strip()
    return bool(name and _LIQUID_WORD.search(name))


def scheme_in_nav_universe(
    scheme_category: str | None, scheme_name_raw: str | None
) -> bool:
    return is_equity_or_hybrid(scheme_category) or is_liquid_fund(
        scheme_category, scheme_name_raw
    )
