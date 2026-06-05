from __future__ import annotations

import json
import re
import requests


def extract_js_object(html: str, var_name: str) -> str:
    start = html.find(f"var {var_name} =")
    if start == -1:
        raise ValueError(f"var {var_name} not found")
    brace_start = html.find("{", start)
    if brace_start == -1:
        raise ValueError("opening { not found")

    i = brace_start
    depth = 0
    in_str = False
    esc = False
    quote = None

    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
                quote = None
        else:
            if ch in ('"', "'"):
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return html[brace_start : i + 1]
        i += 1

    raise ValueError("object end not found")


def main() -> None:
    url = (
        "https://www.etmoney.com/mutual-funds/uti-transportation-and-logistics-fund-direct-growth/"
        "portfolio-details/15522"
    )
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    obj = extract_js_object(html, "getAssetAllocationData")
    print("Extracted chars:", len(obj))
    print("Head:", obj[:220].replace("\n", " "))

    # Best-effort: this should be JSON-ish already; if not, fall back to regex extraction.
    parsed = None
    try:
        parsed = json.loads(obj)
        print("JSON parse: OK. Top keys:", list(parsed.keys())[:20])
    except Exception as e:
        print("JSON parse failed:", type(e).__name__, str(e)[:120])

    if parsed is not None:
        # Helpful introspection: show the shapes of likely allocation lists/maps.
        for k in parsed.keys():
            v = parsed[k]
            if isinstance(v, list):
                print("List key:", k, "len:", len(v))
                if v and isinstance(v[0], dict):
                    print("  first dict keys:", list(v[0].keys())[:30])
            elif isinstance(v, dict):
                print("Dict key:", k, "keys_sample:", list(v.keys())[:10])

        if "mfSectorDTOMap" in parsed:
            secmap = parsed["mfSectorDTOMap"]
            for test_id in ["1", "2", "3", "4", "11", "14", "8"]:
                if test_id in secmap:
                    print("mfSectorDTOMap[", test_id, "] sample:", secmap[test_id])

        # Collect all numeric fields whose key suggests percentage.
        pct_hits: list[tuple[str, float]] = []
        perkey_hits: list[tuple[str, float]] = []

        def walk(x, path: str = "") -> None:
            if isinstance(x, dict):
                for kk, vv in x.items():
                    p2 = f"{path}.{kk}" if path else kk
                    if "percent" in str(kk).lower() and isinstance(vv, (int, float)):
                        pct_hits.append((p2, float(vv)))
                    if (str(kk).lower().endswith("per") or "astper" in str(kk).lower()) and isinstance(vv, (int, float)):
                        perkey_hits.append((p2, float(vv)))
                    walk(vv, p2)
            elif isinstance(x, list):
                for i, vv in enumerate(x):
                    walk(vv, f"{path}[{i}]")

        walk(parsed)
        print("Numeric percent-like fields found:", len(pct_hits))
        for p, v in pct_hits[:20]:
            print(" ", p, "=", v)
        print("Numeric per-like fields found:", len(perkey_hits))
        for p, v in perkey_hits[:20]:
            print(" ", p, "=", v)

        # Heuristic: mfLAHDTOList looks like "sector buckets" with astPer and sId.
        if "mfLAHDTOList" in parsed and "mfSectorDTOMap" in parsed:
            lah = parsed["mfLAHDTOList"]
            sector_map = parsed["mfSectorDTOMap"]
            # Sort by astPer descending, ignore non-numeric.
            def ast_per(rec):
                try:
                    return float(rec.get("astPer"))
                except Exception:
                    return float("-inf")

            top = sorted(lah, key=ast_per, reverse=True)[:12]
            print("\nTop mfLAHDTOList entries (astPer):")
            for rec in top:
                sid = rec.get("sId")
                sector = sector_map.get(str(sid), {}) if sid is not None else {}
                # sector DTOs vary; try common keys
                sec_name = (
                    sector.get("displayName")
                    or sector.get("name")
                    or sector.get("sector")
                    or sector.get("sectorName")
                    or str(sid)
                )
                print(f"  sId={sid}  sector={sec_name}  astPer={rec.get('astPer')}")

            # Pick latest astDt and aggregate by sector.
            dts = [rec.get("astDt") for rec in lah if rec.get("astDt")]
            if dts:
                def norm_dt(x):
                    if isinstance(x, dict):
                        return str(x.get("value") or x.get("date") or "")
                    return str(x)

                normed = [norm_dt(x) for x in dts]
                latest = max(normed) if normed else ""
                latest_rows = [
                    rec for rec in lah if norm_dt(rec.get("astDt")) == latest
                ]
                by_sid: dict[str, float] = {}
                for rec in latest_rows:
                    sid = rec.get("sId")
                    try:
                        val = float(rec.get("astPer"))
                    except Exception:
                        continue
                    if sid is None:
                        continue
                    by_sid[str(int(sid))] = by_sid.get(str(int(sid)), 0.0) + val
                # Convert to readable sector names
                items = []
                for sid, pct in by_sid.items():
                    sec = sector_map.get(sid, {})
                    sec_name = sec.get("sector") or sec.get("displayName") or sec.get("name") or sid
                    items.append((sec_name, pct))
                items.sort(key=lambda x: x[1], reverse=True)
                total = sum(p for _, p in items)
                print(f"\nLatest sector allocation (astDt={latest})")
                print("Total %:", total)
                for name, pct in items[:12]:
                    print(f"  {name:25s} {pct:6.2f}%")

    # Regex fallback: capture displayName + percentage around each other.
    # ET often uses keys like:
    #   "displayName":"Technology", ... "percentage": 12.34
    pairs: list[tuple[str, float]] = []
    rg = re.compile(
        r'"displayName"\s*:\s*"([^"]+)"[^{}]{0,400}?"percentage"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        flags=re.I,
    )
    for m in rg.finditer(obj):
        name = m.group(1).strip()
        pct = float(m.group(2))
        pairs.append((name, pct))

    print("Regex pairs found:", len(pairs))
    for name, pct in pairs[:15]:
        print(f"  {name:40s} {pct:6.2f}%")

    if pairs:
        total = sum(p for _, p in pairs)
        print("Sum of extracted % (may include historical / other lists):", total)


if __name__ == "__main__":
    main()

