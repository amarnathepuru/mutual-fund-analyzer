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
    r"\s*-\s*Direct\s+Plan\s+Growth\s+Plan\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s+Plan\s*$",
    r"\s*-\s*Direct\s+Plan\s+Growth\s+Option\s*$",
    r"\s*-\s*Direct\s+Plan\s*-\s*Growth\s+Option\s*$",
    r"\s*-Direct\s+Plan\s*-\s*Growth\s*$",
    r"\s*-Direct\s+Plan-Growth\s*$",
    r"\s*-\s*Direct\s+Plan-Growth\s*$",
    r"\s*-\s*Growth\s+Plan\s*$",
    r"\s*-\s*GROWTH\s+PLAN\s*$",
    r"\s*\(Direct\)\s*-\s*Growth\s+Option\s*$",
    r"\s*\(Direct\)\s*-\s*Growth\s*$",
    r"\s*-\s*Direct\s*-\s*Growth\s*$",
    r"\s*-\s*Growth\s+Option\s*-\s*Direct\s+Plan\s*$",
    r"\s+Growth\s+Option\s+Direct\s*$",
    r"\s+Growth\s+Direct\s*$",
    r"\s*-Growth-Direct\s*$",
    r"\s*-\s*Direct\s*$",
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


# Tokens ignored when checking MF name coverage against ET (ET lists "… Fund").
_MATCH_STOP: frozenset[str] = frozenset(
    {"fund", "funds", "mutual", "scheme", "plan", "option", "the", "and", "of"}
)


def mf_fund_name_cleaned(scheme_name_raw_or_base: str) -> str:
    """MFAPI Fund Name Cleaned — same as audit CSV / ET Money search label."""
    raw = _nfkc(scheme_name_raw_or_base)
    base = extract_fund_name_base(raw) or raw
    return format_display_fund_name(base)


def mf_match_key(scheme_name_raw_or_base: str) -> str:
    """Normalized key for fuzzy match (plan/option stripped, lowercase)."""
    return normalize_match_key(mf_fund_name_cleaned(scheme_name_raw_or_base))


def et_match_key(et_fund_name: str) -> str:
    """Normalize ET master fund_name (usually already base; strip if needed)."""
    raw = _nfkc(et_fund_name)
    base = extract_fund_name_base(raw) or raw
    return normalize_match_key(base)


def _significant_tokens(match_key: str) -> list[str]:
    return [t for t in match_key.split() if t not in _MATCH_STOP and len(t) > 1]


def mf_significant_tokens(scheme_name_raw_or_base: str) -> set[str]:
    return set(_significant_tokens(mf_match_key(scheme_name_raw_or_base)))


def et_significant_tokens(et_fund_name: str) -> set[str]:
    return set(_significant_tokens(et_match_key(et_fund_name)))


def fund_name_match_score(mf_scheme_or_base: str, et_fund_name: str) -> float:
    """
    0–100 similarity on ET-style fund names only (not MFAPI plan/option suffixes).

    Requires MF tokens to appear in the ET name — avoids Quantum Value → Small Cap.
    """
    from difflib import SequenceMatcher

    mf_key = mf_match_key(mf_scheme_or_base)
    et_key = et_match_key(et_fund_name)
    if not mf_key or not et_key:
        return 0.0
    if mf_key == et_key:
        return 100.0

    ta = " ".join(sorted(mf_key.split()))
    tb = " ".join(sorted(et_key.split()))
    base = SequenceMatcher(None, ta, tb).ratio() * 100.0

    mf_toks = _significant_tokens(mf_key)
    if not mf_toks:
        return base
    mf_set = set(mf_toks)
    et_set = set(_significant_tokens(et_key))
    if not et_set:
        return base * 0.5
    overlap = mf_set & et_set
    mf_cov = len(overlap) / len(mf_set)
    return base * mf_cov


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
    if re.search(r"\bgr\b", lower):
        return "Growth"
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
        # Peel stacked tails (e.g. "- Direct Plan Growth Plan", "- Direct")
        name = re.sub(
            r"\s*-\s*(?:Direct|Regular)\s*(?:Plan\b)?(?:\s*-\s*|\s+)?(?:Growth|IDCW|Dividend|Bonus)\b[\w\s]*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(
            r"\s*-\s*(?:Direct|Regular)\s*(?:Plan\b)?\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(
            r"\s*-\s*(?:Growth|IDCW|GROWTH)\s*(?:Plan|Option)?\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        # Spaced tails without leading dash (e.g. "Fund Direct Plan Growth")
        name = re.sub(
            r"\s+Direct\s+Plan(?:[-\s][\w]+)*\s*(?:Growth|IDCW|Bonus)(?:\s+Option|\s+Plan)?\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(r"\s+Direct\s+Growth\s*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+Direct\s+Plan\s*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+Regular\s+Plan\s*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[-\s]growth\s+Direct\s*$", "", name, flags=re.IGNORECASE)
        name = re.sub(
            r"\s+Direct\s+Plan\s*-\s*Growth\s*\)\s*$",
            ")",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(
            r"\s*\(\s*direct\s*\)\s*Growth\s+Plan\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(
            r"[-\s]+Direct\s+Plan[-\s]+Growth.*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        name = re.sub(r"\s+Direct\s+Growth\s+Option\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*-\s*$", "", name)
    name = re.sub(r"\(\s*\)", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return name


def title_case_words(name: str) -> str:
    """First letter of each word upper, rest lower (display standard)."""
    s = re.sub(r"\s+", " ", _nfkc(name))
    if not s:
        return ""
    return " ".join(
        (w[:1].upper() + w[1:].lower()) if w else "" for w in s.split(" ")
    )


def format_display_fund_name(name: str) -> str:
    """Clean MFAPI/ET label: strip plan/option suffixes, then title-case."""
    base = extract_fund_name_base(name) or _nfkc(name)
    return title_case_words(base)


def parse_scheme_name(scheme_name_raw: str) -> dict[str, str | bool]:
    raw = _nfkc(scheme_name_raw)
    plan = _detect_plan(raw)
    option = _detect_option(raw)
    # MFAPI sometimes uses "Direct Plan" without explicit Growth token.
    if not option and plan == "Direct" and not re.search(
        r"\bidcw\b|income\s+distribution|dividend|bonus|payout|reinvest",
        raw.lower(),
    ):
        option = "Growth"
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
