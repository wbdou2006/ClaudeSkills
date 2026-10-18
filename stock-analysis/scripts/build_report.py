#!/usr/bin/env python3
"""Build the drawdown HTML report straight from the workers' JSON + CSV files.

Headline numbers (price, 52w high, drop %) come from verified.json (my independent
recompute of each worker's raw daily series); narrative, sources and cross-checks
come from each worker's <T>.json.
"""
import csv
import html
import json
from pathlib import Path

import argparse

HERE = Path(__file__).resolve().parent
CSS_PATH = HERE.parent / "assets" / "report.css"
ROOT = Path(".")
TICKERS = []

E = lambda s: html.escape(str(s)) if s is not None else ""


def fmt_money(v, idx=False):
    """Dollars for ETFs/stocks; plain points for indexes."""
    if v is None:
        return "No data"
    return f"{v:,.2f}" if idx else f"${v:,.2f}"


def is_index(w):
    return (w.get("instrument_type") or "").lower() == "index"


def fmt_pct(v, signed=True):
    if v is None:
        return "No data"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def load(t):
    j = ROOT / f"{t}.json"
    w = json.loads(j.read_text()) if j.exists() else {}
    weekly = []
    wp = ROOT / f"{t}_weekly.csv"
    if wp.exists():
        with wp.open() as f:
            rd = csv.DictReader(f)
            cols = [c.strip().lower() for c in (rd.fieldnames or [])]
            date_col = next((c for c in rd.fieldnames or [] if "date" in c.lower() or "week" in c.lower()), None)
            close_col = next((c for c in rd.fieldnames or [] if "close" in c.lower()), None)
            if date_col and close_col:
                for row in rd:
                    try:
                        weekly.append((row[date_col].strip()[:10], float(row[close_col])))
                    except (ValueError, TypeError):
                        continue
    weekly.sort()
    return w, weekly


def sparkline(weekly, high, low, current):
    """Weekly closes with a dashed line at the 52w intraday high. One y-scale for everything."""
    if len(weekly) < 2 or high is None:
        return '<p class="nodata">No weekly series available.</p>'
    W, H, PL, PR, PT, PB = 640, 200, 52, 14, 14, 26
    ys = [c for _, c in weekly] + [high] + ([low] if low else [])
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad
    x = lambda i: PL + i * (W - PL - PR) / (len(weekly) - 1)
    y = lambda v: PT + (hi - v) * (H - PT - PB) / (hi - lo)
    pts = " ".join(f"{x(i):.1f},{y(c):.1f}" for i, (_, c) in enumerate(weekly))
    area = f"{x(0):.1f},{H-PB} " + pts + f" {x(len(weekly)-1):.1f},{H-PB}"
    # 4 gridlines at round-ish values inside the range
    ticks = []
    for k in range(4):
        v = lo + (hi - lo) * (k + 0.5) / 4
        ticks.append(v)
    grid = "".join(
        f'<line x1="{PL}" x2="{W-PR}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
        f'<text x="{PL-6}" y="{y(v)+3.5:.1f}" class="axis" text-anchor="end">{v:,.0f}</text>'
        for v in ticks
    )
    first, last = weekly[0][0], weekly[-1][0]
    mid = weekly[len(weekly) // 2][0]
    xl = (
        f'<text x="{x(0):.1f}" y="{H-8}" class="axis" text-anchor="start">{E(first)}</text>'
        f'<text x="{x(len(weekly)//2):.1f}" y="{H-8}" class="axis" text-anchor="middle">{E(mid)}</text>'
        f'<text x="{x(len(weekly)-1):.1f}" y="{H-8}" class="axis" text-anchor="end">{E(last)}</text>'
    )
    hy = y(high)
    ex, ey = x(len(weekly) - 1), y(weekly[-1][1])
    return f'''<svg viewBox="0 0 {W} {H}" class="spark" role="img" aria-label="Weekly closes over the past 52 weeks against the 52-week high">
  {grid}
  <polygon points="{area}" class="area"/>
  <polyline points="{pts}" class="line" fill="none"/>
  <line x1="{PL}" x2="{W-PR}" y1="{hy:.1f}" y2="{hy:.1f}" class="hiline"/>
  <text x="{W-PR}" y="{hy-5:.1f}" class="hilabel" text-anchor="end">52-wk high {high:,.2f}</text>
  <circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" class="endpt"/>
  {xl}
</svg>'''


def link(title, url):
    if url and str(url).startswith("http"):
        return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(title or url)}</a>'
    return E(title or url or "")


def case_list(items):
    if not items:
        return '<p class="nodata">No data</p>'
    out = []
    for it in items:
        src = link(it.get("source_title"), it.get("url"))
        out.append(
            f'<li><strong>{E(it.get("point"))}</strong>'
            f'<span>{E(it.get("evidence"))}</span>'
            + (f'<cite>{src}</cite>' if src else "")
            + "</li>"
        )
    return "<ul class='case'>" + "".join(out) + "</ul>"


def section(t, w, v, weekly):
    IDX = is_index(w)
    name = (w.get("fund_name") or t).split(" (")[0]
    cp = w.get("current_price") or {}
    hi = w.get("high_52w_intraday") or {}
    cc = w.get("cross_check") or {}
    rets = w.get("returns_pct") or {}
    drivers = w.get("drivers") or []
    holdings = w.get("top_holdings") or []
    gaps = w.get("data_gaps") or []
    er = w.get("expense_ratio") or {}

    cur = v["current"] if v else cp.get("value")
    high = v["high_intraday"] if v else hi.get("value")
    hdate = v["high_intraday_date"] if v else hi.get("date")
    low = v["low_intraday"] if v else (w.get("low_52w_intraday") or {}).get("value")
    drop = v["drop_pct_intraday"] if v else w.get("drop_pct_from_intraday_high")
    dropc = v["drop_pct_close"] if v else w.get("drop_pct_from_closing_high")
    dd = v["drop_dollars"] if v else w.get("drop_dollars")

    ret_cells = "".join(
        f'<div><dt>{lbl}</dt><dd class="{ "neg" if (rets.get(k) or 0) < 0 else "pos"}">{fmt_pct(rets.get(k))}</dd></div>'
        for k, lbl in (("1m", "1 month"), ("3m", "3 months"), ("ytd", "YTD"), ("1y", "1 year"))
    )
    drv = "".join(
        f'<li><div class="drv-head"><strong>{E(d.get("driver"))}</strong>'
        f'<time>{E(d.get("date"))}</time></div><p>{E(d.get("detail"))}</p>'
        f'<cite>{link(d.get("source_title"), d.get("url"))}</cite></li>'
        for d in drivers
    ) or '<li class="nodata">No data</li>'
    hold = "".join(
        f'<tr><td>{E(h.get("symbol") or "")}</td><td>{E(h.get("name") or "")}</td>'
        f'<td class="num">{fmt_pct(h.get("weight_pct"), signed=False) if h.get("weight_pct") is not None else "No data"}</td></tr>'
        for h in holdings[:10]
    )
    hold_tbl = (
        f'<div class="tblwrap"><table class="hold"><thead><tr><th>Symbol</th><th>Holding</th><th class="num">Weight</th></tr></thead>'
        f'<tbody>{hold}</tbody></table></div><p class="src">Holdings: {E(w.get("holdings_source"))}'
        + (f' · as of {E(w.get("holdings_as_of"))}' if w.get("holdings_as_of") else "")
        + "</p>"
        if holdings else '<p class="nodata">Holdings: No data</p>'
    )
    gap_html = (
        "<ul class='gaps'>" + "".join(f"<li>{E(g)}</li>" for g in gaps) + "</ul>"
        if gaps else "<p class='src'>No data gaps reported.</p>"
    )
    cc_line = ""
    if cc:
        cc_line = (
            f'<p class="src">Cross-check ({E(cc.get("source"))}, {E(cc.get("retrieved_at"))}): '
            f'price {fmt_money(cc.get("price"), IDX)}, 52-wk high {fmt_money(cc.get("high_52w"), IDX)}'
            + (f' — {E(cc.get("note"))}' if cc.get("note") else "")
            + "</p>"
        )
    meta = " · ".join(
        x for x in [
            E(w.get("issuer")),
            ("Tracks " + E(w.get("index_tracked"))) if w.get("index_tracked") else "",
            ("Expense ratio " + E(er.get("value")) + "%") if er.get("value") is not None else "",
        ] if x
    )
    return f'''
<section class="fund" id="{t.lower()}">
  <header class="fund-head">
    <div>
      <h2><span class="tkr">{t}</span> {E(name)}</h2>
      <p class="meta">{meta}</p>
    </div>
    <div class="drop-badge"><span class="big">{fmt_pct(drop)}</span><span>from 52-wk high</span></div>
  </header>

  <dl class="facts">
    <div><dt>Last close</dt><dd>{fmt_money(cur, IDX)}</dd><small>{E(cp.get("date") or (v or {}).get("last_date"))}</small></div>
    <div><dt>52-wk high (intraday)</dt><dd>{fmt_money(high, IDX)}</dd><small>{E(hdate)}</small></div>
    <div><dt>Below high</dt><dd>{fmt_money(abs(dd), IDX) if dd is not None else "No data"}</dd><small>{fmt_pct(dropc)} vs closing high</small></div>
    <div><dt>52-wk low</dt><dd>{fmt_money(low, IDX)}</dd><small>{E((v or {}).get("low_intraday_date"))}</small></div>
  </dl>

  <figure>{sparkline(weekly, high, low, cur)}
    <figcaption>Weekly closes, trailing 52 weeks. Dashed line = 52-week intraday high.</figcaption>
  </figure>

  <dl class="rets">{ret_cells}</dl>
  <p class="src">Price source: {E(cp.get("source"))} · retrieved {E(cp.get("retrieved_at"))}. 52-wk high source: {E(hi.get("source"))} · retrieved {E(hi.get("retrieved_at"))}.</p>
  {cc_line}

  <h3>What drove the drop</h3>
  <p class="summary">{E(w.get("drop_summary") or "No data")}</p>
  <ol class="drivers">{drv}</ol>

  <div class="cases">
    <div class="bull"><h3>Bull case</h3>{case_list(w.get("bull_case"))}</div>
    <div class="bear"><h3>Bear case</h3>{case_list(w.get("bear_case"))}</div>
  </div>

  <details>
    <summary>Top holdings, data gaps and calculation log</summary>
    <h4>Top holdings</h4>
    {hold_tbl}
    <h4>Data gaps</h4>
    {gap_html}
    <h4>Calculation output</h4>
    <pre>{E(w.get("calc_output") or "No data")}</pre>
  </details>
</section>'''


def summary_rows(data):
    rows = []
    maxdrop = max((abs(v["drop_pct_intraday"]) for _, _, v, _ in data if v), default=1) or 1
    for t, w, v, _ in data:
        IDX = is_index(w)
        if not v:
            rows.append(f"<tr><td class='tkr'>{t}</td><td colspan='5' class='nodata'>No data</td></tr>")
            continue
        pct = abs(v["drop_pct_intraday"])
        width = pct / maxdrop * 100
        rows.append(
            f"<tr><td><a class='tkr' href='#{t.lower()}'>{t}</a><div class='fname'>{E((w.get('fund_name') or '').split(' (')[0])}</div></td>"
            f"<td class='num'>{fmt_money(v['current'], IDX)}</td>"
            f"<td class='num'>{fmt_money(v['high_intraday'], IDX)}<div class='sub'>{E(v['high_intraday_date'])}</div></td>"
            f"<td class='num neg'>{fmt_pct(v['drop_pct_intraday'])}</td>"
            f"<td class='barcell'><div class='bar' style='width:{width:.1f}%'></div></td>"
            f"<td class='num'>{v['days_since_high']}</td></tr>"
        )
    return "".join(rows)


def main():
    verified = json.loads((ROOT / "verified.json").read_text())
    data = []
    for t in TICKERS:
        w, weekly = load(t)
        data.append((t, w, verified.get(t), weekly))
    last_dates = sorted({v["last_date"] for _, _, v, _ in data if v})
    asof = last_dates[-1] if last_dates else "No data"
    css = CSS_PATH.read_text()
    body = "".join(section(t, w, v, wk) for t, w, v, wk in data)
    page = f'''<title>{E(TITLE)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap">
<style>{css}</style>
<main class="wrap">
  <header class="top">
    <p class="eyebrow">{E(EYEBROW)} · prices as of close {E(asof)}</p>
    <h1>How far {E(ticker_phrase(TICKERS))} {"sits" if len(TICKERS)==1 else "sit"} below {"its" if len(TICKERS)==1 else "their"} 52-week high{"" if len(TICKERS)==1 else "s"}</h1>
    <p class="lede">Each ticker was researched by a separate worker. Every price comes from a market-data tool call with its source and timestamp, and every drop was recomputed in code from the saved daily series. Where a source had nothing, the report says "No data".</p>
  </header>

  <section class="overview">
    <div class="tblwrap"><table class="sum">
      <thead><tr><th>ETF</th><th class="num">Last close</th><th class="num">52-wk high</th><th class="num">Drop</th><th>Distance below high</th><th class="num">Sessions since high</th></tr></thead>
      <tbody>{summary_rows(data)}</tbody>
    </table></div>
    <p class="src">Drop = last close ÷ 52-week intraday high − 1. Window: trailing 365 calendar days ending on the last trading date.</p>
  </section>

  {body}

  <footer class="foot">
    <p>Method: daily OHLC pulled per fund and saved to CSV; 52-week high, % drop, returns and weekly series computed in Python, then re-derived independently from the same CSV before publishing. Narrative and bull/bear points are summarised from the cited sources. This is research, not investment advice.</p>
  </footer>
</main>'''
    OUT.write_text(page)
    print("wrote", OUT, len(page), "bytes")


def ticker_phrase(ts):
    return ts[0] if len(ts) == 1 else ", ".join(ts[:-1]) + " and " + ts[-1]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the drawdown HTML report from worker JSON + verified.json")
    ap.add_argument("--dir", default=".", help="folder with <T>.json, <T>_weekly.csv and verified.json")
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--out", default="drawdown_report.html")
    ap.add_argument("--title", default="52-Week Drawdowns", help="2-4 word page name")
    ap.add_argument("--eyebrow", default="Drawdown review")
    a = ap.parse_args()
    ROOT, OUT, TICKERS = Path(a.dir), Path(a.out), [t.upper() for t in a.tickers]
    TITLE, EYEBROW = a.title, a.eyebrow
    main()
