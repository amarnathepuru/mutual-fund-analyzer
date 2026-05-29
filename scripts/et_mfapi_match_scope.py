"""
Which ET ACTIVE funds participate in MFAPI NAV matching.

Index funds are excluded: MFAPI nav universe is Equity + Hybrid + Liquid only.
"""
from __future__ import annotations

import re

_INDEX_IN_CATEGORY = re.compile(r"\bindex\b", re.IGNORECASE)
_INDEX_IN_NAME = re.compile(r"\bindex\b", re.IGNORECASE)


def is_et_index_fund(category: str | None, fund_name: str | None) -> bool:
    cat = (category or "").strip()
    name = (fund_name or "").strip()
    if cat and _INDEX_IN_CATEGORY.search(cat):
        return True
    if name and _INDEX_IN_NAME.search(name):
        return True
    return False


def et_index_mask(df) -> "object":
    """Boolean series for ET master rows that are index funds."""
    return df.apply(
        lambda r: is_et_index_fund(r.get("category"), r.get("fund_name")),
        axis=1,
    )
