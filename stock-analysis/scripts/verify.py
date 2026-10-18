#!/usr/bin/env python3
"""Independent check of every worker's output before the report is built.

For each ticker it re-derives the headline numbers from <T>_daily.csv and compares
them with <T>.json, checks that required fields, sources and timestamps exist,
and writes verified.json (the numbers build_report.py will display).

Usage:
    python3 verify.py --dir work --tickers FTEC QQQ SMH ARTY

Exit code 1 if any MISMATCH or missing required field, so the run stops before
a bad report is published.
"""
import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

TOL = 0.01
REQUIRED = ["ticker", "fund_name", "last_trading_date", "current_price", "high_52w_intraday",
            "drop_pct_from_intraday_high", "drop_summary", "drivers", "bull_case", "bear_case", "data_gaps"]


def load_daily(p):
    rows = []
    with p.open() as f:
        rd = csv.DictReader(f)
        fields = {c.lower().strip(): c for c in (rd.fieldnames or [])}
        for r in rd:
            try:
                rows.append({"date": date.fromisoformat(r[fields["date"]].strip()[:10]),
                             "high": float(r[fields["high"]]), "low": float(r[fields["low"]]),
                             "close": float(r[fields["close"]])})
            except (KeyError, ValueError, TypeError):
                continue
    d = {r["date"]: r for r in rows}
    return [d[k] for k in sorted(d)]


def recompute(rows):
    last = rows[-1]
    win = [r for r in rows if r["date"] >= last["date"] - timedelta(days=365)]
    hi = max(win, key=lambda r: r["high"]); hc = max(win, key=lambda r: r["close"]); lo = min(win, key=lambda r: r["low"])
    cur = last["close"]
    return {"last_date": last["date"].isoformat(), "window_start": win[0]["date"].isoformat(), "n_days": len(win),
            "current": cur, "high_intraday": hi["high"], "high_intraday_date": hi["date"].isoformat(),
            "high_close": hc["close"], "high_close_date": hc["date"].isoformat(),
            "low_intraday": lo["low"], "low_intraday_date": lo["date"].isoformat(),
            "drop_pct_intraday": round((cur / hi["high"] - 1) * 100, 4),
            "drop_pct_close": round((cur / hc["close"] - 1) * 100, 4),
            "drop_dollars": round(cur - hi["high"], 4),
            "days_since_high": sum(1 for r in win if r["date"] > hi["date"])}


def g(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--tickers", nargs="+", required=True)
    a = ap.parse_args()
    root = Path(a.dir)
    out, problems = {}, 0

    def chk(label, mine, theirs, tol=TOL):
        nonlocal problems
        if theirs is None:
            problems += 1
            return f"  [MISSING] {label}: worker gave nothing (recomputed {mine})"
        try:
            ok = abs(float(mine) - float(theirs)) <= tol
        except (TypeError, ValueError):
            ok = str(mine) == str(theirs)
        problems += 0 if ok else 1
        return f"  [{'OK' if ok else 'MISMATCH'}] {label}: recomputed={mine} worker={theirs}"

    for t in [x.upper() for x in a.tickers]:
        print(f"=== {t} ===")
        dp, jp = root / f"{t}_daily.csv", root / f"{t}.json"
        rows = load_daily(dp) if dp.exists() else []
        if not rows:
            print("  [NO DATA] daily CSV missing or empty — report will show No data")
            out[t] = None
            continue
        rc = recompute(rows); out[t] = rc
        print(f"  window {rc['window_start']}..{rc['last_date']} ({rc['n_days']} sessions)")
        if not jp.exists():
            print("  [NO JSON] worker JSON missing"); problems += 1; continue
        w = json.loads(jp.read_text())
        for k in REQUIRED:
            if w.get(k) in (None, "", []) and k != "data_gaps":
                print(f"  [MISSING FIELD] {k}"); problems += 1
        print(chk("last_trading_date", rc["last_date"], w.get("last_trading_date")))
        print(chk("current_price", rc["current"], g(w, "current_price", "value")))
        print(chk("high_52w_intraday", rc["high_intraday"], g(w, "high_52w_intraday", "value")))
        print(chk("high_52w_intraday date", rc["high_intraday_date"], g(w, "high_52w_intraday", "date")))
        print(chk("high_52w_close", rc["high_close"], g(w, "high_52w_close", "value")))
        print(chk("low_52w_intraday", rc["low_intraday"], g(w, "low_52w_intraday", "value")))
        print(chk("drop_pct_from_intraday_high", rc["drop_pct_intraday"], w.get("drop_pct_from_intraday_high")))
        print(chk("drop_pct_from_closing_high", rc["drop_pct_close"], w.get("drop_pct_from_closing_high")))
        print(chk("drop_dollars", rc["drop_dollars"], w.get("drop_dollars")))
        for k in ("current_price", "high_52w_intraday"):
            s, ts = g(w, k, "source"), g(w, k, "retrieved_at")
            if not (s and ts):
                problems += 1
            print(f"  [{'OK' if s and ts else 'NO SOURCE/TS'}] {k} source/timestamp")
        cc = w.get("cross_check") or {}
        if cc.get("price") is not None:
            diff = (float(cc["price"]) / rc["current"] - 1) * 100
            flag = "OK" if abs(diff) <= 0.5 else "DISAGREE >0.5%"
            print(f"  [{flag}] cross-check price {cc['price']} ({diff:+.3f}%)")
        else:
            print("  [NO CROSS-CHECK] no second-source price")
        for k in ("drivers", "bull_case", "bear_case"):
            uncited = [i for i in (w.get(k) or []) if not i.get("url") and not i.get("source_title")]
            if uncited:
                print(f"  [UNCITED] {len(uncited)} item(s) in {k} lack a source")
        print(f"  drivers={len(w.get('drivers') or [])} bull={len(w.get('bull_case') or [])} "
              f"bear={len(w.get('bear_case') or [])} gaps={len(w.get('data_gaps') or [])}")

    (root / "verified.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {root / 'verified.json'} — problems: {problems}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
