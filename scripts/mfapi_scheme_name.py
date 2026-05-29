"""
Parse MFApi scheme_name into fund name, plan (Direct/Regular), and option (Growth/IDCW/...).

ET Money fund names omit plan/option; fund_name_base is intended for ET matching.
"""
from __future__ import annotations

import re
import unicodedata

# Longest-first suffix patterns (case-insensitive) stripped to derive fund_name_base.
_STRIP_SUFFIXES: tuple[str, ...] = (
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*-\s*DIRECT\s+PLAN\s*-\s*GROWTH\s+OPTION\s*$",
    r"\s*-\s*Direct\s+Plan\s+Growth\s+Option\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*GROWTH\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*Direct\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*Direct\s+Plan\s*-\s*Growth\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*-Direct\s+Plan\s*-\s*Growth\s*$",
    r"\s*-Direct\s+Plan-Growth\s*$",
    r"\s*-\s*Direct\s+Plan-Growth\s*$",
    r"\s*\(Direct\)\s*-\s*Growth\s+Option\s*$",
    r"\s*\(Direct\)\s*-\s*Growth\s*$",
    r"\s*-\s*Direct\s*-\s*Growth\s*$",
    r"\s*-\s*Growth\s+Option\s*-\s*Direct\s+Plan\s*$",
    r"\s+Growth\s+Option\s+Direct\s*$",
    r"\s+Growth\s+Direct\s*$",
    r"\s*-Growth-Direct\s*$",
    r"\s*-Direct\s*$",
    r"\s*\(Direct\)\s*$",
    r"\s*-\s*Direct\s+Plan\s*$",
    r"\s*Direct\s+Plan\s*$",
    r"\s*-\s*Growth\s+Option\s*$",
    r"\s*-\s*Growth\s*$",
    r"\s*-\s*GROWTH\s+OPTION\s*$",
    r"\s*-\s*GROWTH\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Dividend\s*$",
    r"\s*-Direct\s+Plan-Dividend\s*$",
    r"\s*-\s*Regular\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*\(Regular\)\s*-\s*Growth\s*$",
    r"\s*\(Regular\)\s*-\s*IDCW\s*$",
    r"\s*-\s*Regular\s+Plan\s*-\s*IDCW\s*$",
)

_STRIP_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _STRIP_SUFFIXES)

# Attached "Index-Direct Plan" → insert break before Direct for stripping
_ATTACHED_DIRECT = re.compile(
    r"(?<=[a-zA-Z0-9])(-Direct\s+Plan)",
    re.IGNORECASE,
)


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()


def normalize_match_key(name: str) -> str:
    """Lowercase alphanumeric key for fuzzy ET matching (later batches)."""
    s = _nfkc(name).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _detect_plan(name: str) -> str:
    lower = name.lower()
    if re.search(r"\bregular\b", lower):
        return "Regular"
    if re.search(
        r"direct\s+plan|\(direct\)|\bdirect\b|-direct\b|growth\s+direct\b|direct\s*$",
        lower,
    ):
        return "Direct"
    return ""


def _detect_option(name: str) -> str:
    lower = name.lower()
    if re.search(
        r"\bidcw\b|income\s+distribution|dividend|div\s+reinvest|dividend\s+reinvest",
        lower,
    ):
        if "reinvest" in lower or "reinv" in lower:
            return "DividendReinvest"
        return "IDCW"
    if re.search(r"\bbonus\b", lower):
        return "Bonus"
    if re.search(r"\bgrowth\b", lower):
        return "Growth"
    return ""


def is_direct_growth(plan: str, option: str, scheme_name_raw: str) -> bool:
    if plan != "Direct" or option != "Growth":
        return False
    lower = scheme_name_raw.lower()
    if re.search(r"\bregular\b", lower):
        return False
    if re.search(
        r"\bidcw\b|dividend|income\s+distribution|weekly|monthly|quarterly",
        lower,
    ):
        return False
    return True


def extract_fund_name_base(scheme_name_raw: str) -> str:
    """Remove plan/option suffixes; keep core fund name as ET would list it."""
    name = _nfkc(scheme_name_raw)
    name = _ATTACHED_DIRECT.sub(r" - Direct Plan", name)
    prev = None
    while prev != name:
        prev = name
        for pat in _STRIP_COMPILED:
            name = pat.sub("", name)
    name = re.sub(r"\s*-\s*$", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return name


def parse_scheme_name(scheme_name_raw: str) -> dict[str, str | bool]:
    raw = _nfkc(scheme_name_raw)
    plan = _detect_plan(raw)
    option = _detect_option(raw)
    base = extract_fund_name_base(raw)
    dg = is_direct_growth(plan, option, raw)
    return {
        "scheme_name_raw": raw,
        "fund_name_base": base,
        "fund_name_match_key": normalize_match_key(base),
        "plan_type": plan,
        "option_type": option,
        "is_direct_growth": dg,
    }
