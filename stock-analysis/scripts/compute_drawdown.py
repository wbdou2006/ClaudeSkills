#!/usr/bin/env python3
"""Compute 52-week drawdown metrics from a saved daily OHLC CSV.

Every number in the report's price section comes from this script, never from
hand arithmetic or memory.

Usage:
    python3 compute_drawdown.py --ticker SMH --daily work/SMH_daily.csv --out-dir work

Input CSV columns (header required, extra columns ignored):
    date,open,high,low,close[,volume]

Writes:
    <out-dir>/<TICKER>_metrics.json   headline numbers (paste into <TICKER>.json)
    <out-dir>/<TICKER>_weekly.csv     week_ending,close  (used for the chart)
and prints a human-readable log; copy that stdout into "calc_output".
"""
import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path


def load(path):
    rows = []
    with open(path) as f:
        rd = csv.DictReader(f)
        fields = {c.lower().strip(): c for c in (rd.fieldnames or [])}
        need = ["date", "high", "low", "close"]
        missing = [c for c in need if c not in fields]
        if missing:
            sys.exit(f"CSV is missing columns: {missing}. Found: {rd.fieldnames}")
        for r in rd:
            try:
                rows.append({
                    "date": date.fromisoformat(r[fields["date"]].strip()[:10]),
                    "high": float(r[fields["high"]]),
                    "low": float(r[fields["low"]]),
                    "close": float(r[fields["close"]]),
                })
            except (ValueError, TypeError):
                continue
    rows.sort(key=lambda r: r["date"])
    # de-duplicate dates (keep last occurrence)
    dedup = {}
    for r in rows:
        dedup[r["date"]] = r
    return [dedup[d] for d in sorted(dedup)]


def pct(a, b):
    return None if not b else round((a / b - 1) * 100, 4)


def close_n_back(rows, n):
    return rows[-1 - n] if len(rows) > n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--daily", required=True)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--window-days", type=int, default=365, help="calendar days in the lookback window")
    a = ap.parse_args()

    t = a.ticker.upper()
    rows = load(a.daily)
    if len(rows) < 30:
        sys.exit(f"Only {len(rows)} usable rows in {a.daily}; need about a year of daily bars.")

    last = rows[-1]
    start = last["date"] - timedelta(days=a.window_days)
    win = [r for r in rows if r["date"] >= start]
    coverage_ok = rows[0]["date"] <= start + timedelta(days=7)

    hi = max(win, key=lambda r: r["high"])
    hc = max(win, key=lambda r: r["close"])
    lo = min(win, key=lambda r: r["low"])
    cur = last["close"]

    # returns
    def ret_from(row):
        return None if row is None else pct(cur, row["close"])

    prev_year_end = [r for r in rows if r["date"].year < last["date"].year]
    ytd_base = prev_year_end[-1] if prev_year_end else None
    y1_base = win[0] if coverage_ok else None

    # suspicious one-day jumps (possible unadjusted split)
    jumps = []
    for p, q in zip(rows, rows[1:]):
        ch = q["close"] / p["close"] - 1
        if abs(ch) > 0.25:
            jumps.append(f"{q['date']}: {ch*100:+.1f}% close-to-close")

    # weekly closes (last session of each ISO week) inside the window
    weekly = {}
    for r in win:
        y, w, _ = r["date"].isocalendar()
        weekly[(y, w)] = r
    weekly_rows = [weekly[k] for k in sorted(weekly)]

    m = {
        "ticker": t,
        "last_trading_date": last["date"].isoformat(),
        "window_start": win[0]["date"].isoformat(),
        "sessions_in_window": len(win),
        "full_window_coverage": coverage_ok,
        "current_price": round(cur, 4),
        "high_52w_intraday": {"value": round(hi["high"], 4), "date": hi["date"].isoformat()},
        "high_52w_close": {"value": round(hc["close"], 4), "date": hc["date"].isoformat()},
        "low_52w_intraday": {"value": round(lo["low"], 4), "date": lo["date"].isoformat()},
        "drop_pct_from_intraday_high": pct(cur, hi["high"]),
        "drop_pct_from_closing_high": pct(cur, hc["close"]),
        "drop_dollars": round(cur - hi["high"], 4),
        "trading_days_since_high": sum(1 for r in win if r["date"] > hi["date"]),
        "above_low_pct": pct(cur, lo["low"]),
        "returns_pct": {
            "1m": ret_from(close_n_back(rows, 21)),
            "3m": ret_from(close_n_back(rows, 63)),
            "ytd": ret_from(ytd_base),
            "1y": ret_from(y1_base),
            "basis": "price only, close-to-close; 1m=21 sessions, 3m=63 sessions, YTD vs prior year-end close, 1y vs window start",
        },
        "possible_split_jumps": jumps,
    }

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{t}_metrics.json").write_text(json.dumps(m, indent=2))
    with open(out / f"{t}_weekly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["week_ending", "close"])
        for r in weekly_rows:
            w.writerow([r["date"].isoformat(), r["close"]])

    print(f"{t}: {len(rows)} rows, window {m['window_start']}..{m['last_trading_date']} ({len(win)} sessions)")
    if not coverage_ok:
        print(f"WARNING: data starts {rows[0]['date']}, after window start {start}; 52-week figures cover a shorter span.")
    print(f"Last close           {cur:,.4f} on {m['last_trading_date']}")
    print(f"52w intraday high    {hi['high']:,.4f} on {hi['date']}")
    print(f"52w closing high     {hc['close']:,.4f} on {hc['date']}")
    print(f"52w intraday low     {lo['low']:,.4f} on {lo['date']}")
    print(f"Drop from intraday high  {m['drop_pct_from_intraday_high']:+.4f}%  ({m['drop_dollars']:+,.4f})")
    print(f"Drop from closing high   {m['drop_pct_from_closing_high']:+.4f}%")
    print(f"Sessions since high      {m['trading_days_since_high']}")
    for k in ("1m", "3m", "ytd", "1y"):
        v = m["returns_pct"][k]
        print(f"Return {k:<4} {'No data' if v is None else f'{v:+.4f}%'}")
    if jumps:
        print("CHECK SPLITS — large one-day moves:", "; ".join(jumps))
    print(f"wrote {out / (t + '_metrics.json')} and {out / (t + '_weekly.csv')}")


if __name__ == "__main__":
    main()
