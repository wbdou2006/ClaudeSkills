---
name: stock-analysis
description: Research how far stocks or ETFs sit below their 52-week high, why they fell, and the bull and bear case, then save a consistent HTML report to the working directory and present it to the user, and, if the user gives an email address, prepare a ready-to-send email of it. With no tickers named it uses a default watchlist (XLK, FTEC, QQQ, SMH, ARTY, S&P 500, Dow Jones). Use whenever the user lists tickers or asks for a market check, 52-week highs, drawdowns, "how much has X dropped", pullback analysis, or a drop/bull/bear report, even if they don't say "report".
---

# Stock analysis

This skill produces the same report every time:
- an overview table
- one panel per ticker, containing:
  - facts
  - a weekly chart against the 52-week high
  - returns
  - the drivers of the drop
  - the bull and bear cases
  - holdings, data gaps and the calculation log

The scripts do all the arithmetic and the HTML. Your job is the research and the checking. Do not redesign the page or hand-write HTML.

`SKILL_DIR` is the folder containing this file. Find it once with `dirname` on this SKILL.md path.

## Files
| Path | Purpose |
|---|---|
| `scripts/compute_drawdown.py` | daily CSV → 52-week high and low, % drop, returns, weekly closes |
| `scripts/verify.py` | re-derives every headline number from the CSVs, checks fields and sources, writes `verified.json`, exits 1 on any problem |
| `scripts/build_report.py` | worker JSON + `verified.json` → one self-contained HTML page (uses `assets/report.css`) |
| `scripts/build_email.py` | same verified numbers → ready-to-send `drawdown_report.eml` (email-safe HTML + text, report attached); validates the address |
| `scripts/send_email.py` | for the user to run on their own computer: sends the `.eml` over SMTP with a confirmation prompt and a locally entered app password |
| `defaults.json` | the default watchlist used when the user names no tickers (user-editable) |
| `references/worker_brief.md` | the brief each worker follows (fill the `{…}` placeholders) |
| `references/schema.md` | the `<TICKER>.json` contract |
| `examples/run-2026-10-16/` | a complete reference run (FTEC, QQQ, SMH, ARTY): four worker JSONs and the finished `report.html`. Use it as the bar for depth, tone and citation style. |

## Workflow

### 1. Set up
1. Read the ticker list from the user's request.
   - **No tickers named** ("run my stock analysis", "how's the market vs highs?"): read `$SKILL_DIR/defaults.json` and use its `default_watchlist`, in that order. Say in your first line that you're using the default watchlist and list it.
   - **Tickers named:** use exactly those; don't add the defaults unless the user asks (e.g. "the usual plus NVDA").
   - **Indexes** (S&P 500, Dow Jones, Nasdaq Composite…): research the index level itself, using the `id` from `defaults.json` (SPX, DJI) or a short label like `COMP` as the ticker in file names. Tell the worker it's an index (see the brief's index notes).
2. Create a work folder: `WORK_DIR=$PWD/drawdown-<YYYY-MM-DD>`.
3. Create a task list with:
   - one task per ticker
   - "Verify numbers"
   - "Build and save report"

### 2. Fan out
Spawn **one subagent per ticker**, in parallel and in the background. Each one's prompt is:
- the full text of `references/worker_brief.md`,
- with `{TICKER}`, `{WORK_DIR}`, `{SKILL_DIR}` and `{TODAY}` filled in,
- plus any ticker-specific angles worth checking. For a chip fund, for example: export controls, hyperscaler capex, memory cycle.

When the user names only one or two tickers and has not asked for subagents, you may do the research yourself by following the same brief.

### 3. Wait
When a worker finishes, tick its task off and post one line: the ticker, its % drop, and the date of its high. Do not read worker transcripts.

### 4. Verify
Run:
```
python3 $SKILL_DIR/scripts/verify.py --dir $WORK_DIR --tickers <T...>
```

If it reports `MISMATCH`, `MISSING` or `NO SOURCE/TS`, fix the problem before building:
- **Arithmetic or hand-copy errors:** re-run `compute_drawdown.py` and correct the JSON from `<T>_metrics.json`.
- **Missing research:** send the worker back with SendMessage.

`UNCITED` and `NO CROSS-CHECK` are warnings. Mention them in your reply if they remain.

### 5. Build
Run:
```
python3 $SKILL_DIR/scripts/build_report.py --dir $WORK_DIR --tickers <T...> \
  --out $WORK_DIR/drawdown_report.html --title "<2-4 word name>" --eyebrow "<e.g. ETF drawdown review>"
```

**Choosing the title:** pick a short, specific name, such as "Tech ETF Drawdowns" or "Chip Stock Pullbacks". Use the same title for repeat runs on the same basket.

### 6. Save and present
The build step already wrote the report to `$WORK_DIR/drawdown_report.html`. Do not publish it with the Artifact tool and do not upload it anywhere — it stays local to `$WORK_DIR`.

- Tell the user the absolute path to `drawdown_report.html`.
- Present it to them directly: open it with the browser-preview tool if one is available, or whatever "show this HTML file" capability exists in the current environment.
- **Repeat run on the same basket:** reuse the same `$WORK_DIR` (or tell the user where the new one is) rather than trying to keep a stable published link — there isn't one.
- **Do not edit the generated HTML by hand.** Report-wide changes belong in `build_report.py` or `assets/report.css`.

### 7. Email (only when the user gave an address)
Skip this step unless the user's own message includes an email address, e.g. "…and email it to ana@example.com". If they say "email it to me" without an address, ask for one; never guess or reuse an address from elsewhere.

**No connectors.** Do not use Gmail, Outlook or any other email connector or browser automation, and never ask for or handle an email password. Sending happens on the user's side: you prepare a ready-to-send message, the user sends it.

1. **Build the email.**
   ```
   python3 $SKILL_DIR/scripts/build_email.py --dir $WORK_DIR --tickers <T...> --to <address...> \
     --report $WORK_DIR/drawdown_report.html --title "<same title>"
   ```
   Exit code 2 means the address is invalid: ask the user to correct it. The script writes `drawdown_report.eml` (HTML + plain text, report attached, recipients and subject filled in), plus `email_body.html`, `email_body.txt` and `email.json`. There is no published link to pass — the full report only reaches the recipient as the attached HTML file.
2. **Deliver it.** Send `drawdown_report.eml` with SendUserFile (display `attach`).
3. **Tell the user how to send it**, in two or three lines:
   - Open the `.eml` in Outlook (opens as a draft) or Apple Mail (Message → Send Again), check it, and press Send.
   - Or, from Terminal on their own computer: `python3 send_email.py drawdown_report.eml --from <their address>`. The script shows the recipients, asks for confirmation, and prompts for an app password itself. Send `scripts/send_email.py` too if they ask for it.

### 8. Reply
Keep the reply short:
1. One sentence saying what the page is.
2. A markdown table sorted by drop, with columns: ticker, last close, 52-week high (date), drop.
3. Two or three bullets with the main findings across tickers.
4. A short "Data gaps" note covering the tool failures that affected the run.
5. If an email was requested: one line saying the `.eml` is ready to send and how.

Do not recap the steps.

## Non-negotiables
1. **Every number comes from a tool call**, with its source and its timestamp.
2. **"No data" beats a guess.**
3. **All math is done in the scripts.**
4. **Read-only tools only.** Never touch order, alert or watchlist tools. Never send email yourself; step 7 only prepares a message for the user to send.
5. **No buy or sell recommendation.** Present both cases fairly.
