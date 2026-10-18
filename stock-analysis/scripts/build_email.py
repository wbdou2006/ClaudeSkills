#!/usr/bin/env python3
"""Build an email version of the drawdown report.

Email clients strip <style> blocks, web fonts and SVG, so this writes a separate,
email-safe body (inline styles, table layout, CSS bars instead of charts) built
from the same verified numbers as the HTML report. The full interactive report
goes along as an .html attachment and/or the artifact link.

Usage:
    python3 build_email.py --dir work --tickers FTEC QQQ SMH ARTY \
        --to someone@example.com --report work/drawdown_report.html \
        [--artifact-url https://claude.ai/artifact/...] [--title "Tech ETF Drawdowns"]

Writes to --dir:
    email.json        {"to", "subject", "attachment", "artifact_url", "text_path", "html_path", "eml_path"}
    drawdown_report.eml  ready-to-send message (HTML + text + report attached). Open it in
                         Apple Mail / Outlook and send; or send it with send_email.py.
    email_body.html   inline-styled HTML body
    email_body.txt    plain-text body (for connectors that only take text)
Exits 2 if --to is not a valid-looking address.
"""
import argparse
import html
import json
import re
import sys
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

E = lambda s: html.escape(str(s)) if s is not None else ""
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

INK, MUTED, LINE, LOSS, ACCENT, BG = "#142033", "#586880", "#D6DCE5", "#B8372A", "#1F5FBF", "#F2F4F7"
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, Menlo, Consolas, monospace"


def money(v, idx=False):
    if v is None:
        return "No data"
    return f"{v:,.2f}" if idx else f"${v:,.2f}"


def is_index(w):
    return (w.get("instrument_type") or "").lower() == "index"


def pct(v):
    return "No data" if v is None else f"{v:+.2f}%"


def short_name(w):
    return (w.get("fund_name") or "").split(" (")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--to", required=True, nargs="+", help="one or more recipient addresses")
    ap.add_argument("--report", help="path of the built HTML report to attach")
    ap.add_argument("--artifact-url", help="published report link (private unless shared)")
    ap.add_argument("--title", default="52-Week Drawdowns")
    a = ap.parse_args()

    bad = [x for x in a.to if not EMAIL_RE.match(x.strip())]
    if bad:
        print(f"Not a valid email address: {', '.join(bad)}", file=sys.stderr)
        sys.exit(2)

    root = Path(a.dir)
    verified = json.loads((root / "verified.json").read_text())
    tickers = [t.upper() for t in a.tickers]
    data = []
    for t in tickers:
        jp = root / f"{t}.json"
        w = json.loads(jp.read_text()) if jp.exists() else {}
        data.append((t, w, verified.get(t)))

    asof = max((v["last_date"] for _, _, v in data if v), default="No data")
    ranked = sorted(data, key=lambda d: d[2]["drop_pct_intraday"] if d[2] else 0)
    maxdrop = max((abs(v["drop_pct_intraday"]) for _, _, v in data if v), default=1) or 1
    subject = f"{a.title}: {', '.join(tickers)} vs 52-week highs (close {asof})"

    # ---------- plain text ----------
    tl = [f"{a.title} — prices as of close {asof}", ""]
    tl.append(f"{'Ticker':<7}{'Last close':>12}{'52-wk high':>12}  {'High date':<11}{'Drop':>9}")
    for t, w, v in ranked:
        if not v:
            tl.append(f"{t:<7}  No data"); continue
        tl.append(f"{t:<7}{money(v['current'], is_index(w)):>12}{money(v['high_intraday'], is_index(w)):>12}  "
                  f"{v['high_intraday_date']:<11}{pct(v['drop_pct_intraday']):>9}")
    tl.append("")
    for t, w, v in ranked:
        tl.append(f"{t} — {short_name(w)}")
        tl.append(w.get("drop_summary") or "No data")
        for d in (w.get("drivers") or [])[:3]:
            tl.append(f"  • {d.get('driver')} ({d.get('date')})")
        tl.append("")
    if a.artifact_url:
        tl.append(f"Full report: {a.artifact_url}")
    if a.report:
        tl.append("The full report with charts, bull/bear cases and sources is attached as an HTML file.")
    tl += ["", "Every price comes from a market-data tool call and every drop was recomputed in code. "
           "Research only, not investment advice."]
    text = "\n".join(tl)

    # ---------- inline-styled HTML ----------
    td = f"padding:10px 12px;border-bottom:1px solid {LINE};font-family:{FONT};font-size:14px;color:{INK};"
    tdn = td + f"text-align:right;font-family:{MONO};white-space:nowrap;"
    th = (f"padding:8px 12px;border-bottom:1px solid {LINE};font-family:{MONO};font-size:11px;"
          f"letter-spacing:.05em;text-transform:uppercase;color:{MUTED};text-align:left;font-weight:500;")
    rows = []
    for t, w, v in ranked:
        if not v:
            rows.append(f'<tr><td style="{td}"><b>{t}</b></td><td colspan="4" style="{td}color:{MUTED};"><i>No data</i></td></tr>')
            continue
        width = max(2, round(abs(v["drop_pct_intraday"]) / maxdrop * 120))
        rows.append(
            f'<tr><td style="{td}"><b style="font-family:{MONO};color:{ACCENT};">{t}</b>'
            f'<div style="font-size:12px;color:{MUTED};">{E(short_name(w))}</div></td>'
            f'<td style="{tdn}">{money(v["current"], is_index(w))}</td>'
            f'<td style="{tdn}">{money(v["high_intraday"], is_index(w))}<div style="font-size:11px;color:{MUTED};">{E(v["high_intraday_date"])}</div></td>'
            f'<td style="{tdn}color:{LOSS};"><b>{pct(v["drop_pct_intraday"])}</b></td>'
            f'<td style="{td}width:130px;"><div style="height:10px;width:{width}px;background:{LOSS};border-radius:2px;"></div></td></tr>'
        )
    sections = []
    for t, w, v in ranked:
        drivers = "".join(
            f'<li style="margin:0 0 6px;"><b>{E(d.get("driver"))}</b> '
            f'<span style="color:{MUTED};font-family:{MONO};font-size:12px;">{E(d.get("date"))}</span></li>'
            for d in (w.get("drivers") or [])[:3]
        )
        bull = (w.get("bull_case") or [{}])[0].get("point")
        bear = (w.get("bear_case") or [{}])[0].get("point")
        sections.append(
            f'<tr><td style="padding:18px 0 4px;font-family:{FONT};">'
            f'<div style="font-size:17px;font-weight:600;color:{INK};"><span style="font-family:{MONO};color:{ACCENT};">{t}</span> {E(short_name(w))}'
            f' <span style="color:{LOSS};font-family:{MONO};font-size:15px;">{pct(v["drop_pct_intraday"]) if v else "No data"}</span></div>'
            f'<p style="margin:6px 0 8px;font-size:14px;line-height:1.5;color:{INK};">{E(w.get("drop_summary") or "No data")}</p>'
            f'<ul style="margin:0 0 8px 18px;padding:0;font-size:14px;color:{INK};">{drivers}</ul>'
            + (f'<p style="margin:0;font-size:13px;color:{INK};"><b style="color:#1B7A50;">Bull:</b> {E(bull)}<br>'
               f'<b style="color:{LOSS};">Bear:</b> {E(bear)}</p>' if bull or bear else "")
            + "</td></tr>"
        )
    link_html = (f'<p style="margin:16px 0 0;font-family:{FONT};font-size:14px;">'
                 f'<a href="{E(a.artifact_url)}" style="color:{ACCENT};">Open the full report</a></p>') if a.artifact_url else ""
    attach_html = (f'<p style="margin:8px 0 0;font-family:{FONT};font-size:13px;color:{MUTED};">'
                   f'The full report with charts, bull/bear cases and sources is attached as an HTML file '
                   f'(open it in any browser).</p>') if a.report else ""
    body = f'''<!doctype html><html><body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;border:1px solid {LINE};border-radius:8px;">
<tr><td style="padding:22px 24px 8px;font-family:{FONT};">
  <div style="font-family:{MONO};font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};">{E(a.title)} · prices as of close {E(asof)}</div>
  <h1 style="margin:6px 0 0;font-size:22px;line-height:1.25;color:{INK};">How far {E(", ".join(tickers))} sit below their 52-week highs</h1>
</td></tr>
<tr><td style="padding:12px 24px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr><th style="{th}">Ticker</th><th style="{th}text-align:right;">Last close</th><th style="{th}text-align:right;">52-wk high</th><th style="{th}text-align:right;">Drop</th><th style="{th}">&nbsp;</th></tr>
    {"".join(rows)}
  </table>
</td></tr>
<tr><td style="padding:0 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(sections)}</table></td></tr>
<tr><td style="padding:8px 24px 22px;">{link_html}{attach_html}
  <p style="margin:14px 0 0;font-family:{FONT};font-size:12px;color:{MUTED};">Every price comes from a market-data tool call and every drop was recomputed in code. Research only, not investment advice.</p>
</td></tr>
</table></td></tr></table></body></html>'''

    (root / "email_body.html").write_text(body)
    (root / "email_body.txt").write_text(text)
    # ready-to-send .eml (X-Unsent makes Outlook open it as an editable draft)
    msg = EmailMessage()
    msg["To"] = ", ".join(x.strip() for x in a.to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["X-Unsent"] = "1"
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    if a.report:
        rp = Path(a.report)
        msg.add_attachment(rp.read_bytes(), maintype="text", subtype="html", filename=rp.name)
    eml = root / "drawdown_report.eml"
    eml.write_bytes(bytes(msg))

    meta = {"to": [x.strip() for x in a.to], "subject": subject, "eml_path": str(eml.resolve()),
            "attachment": str(Path(a.report).resolve()) if a.report else None,
            "artifact_url": a.artifact_url,
            "html_path": str((root / "email_body.html").resolve()),
            "text_path": str((root / "email_body.txt").resolve())}
    (root / "email.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
