# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A single Claude Code **skill** (`SKILL.md`) called `stock-analysis`. It is not an application — there is no server, no build, no test suite, and no package manifest. It's invoked when a user asks about a stock/ETF's drawdown from its 52-week high, drivers of a drop, or wants a bull/bear report. The skill's full workflow (how to fan out research subagents, what order to run scripts in, how to verify, publish and optionally email) is already written out in `SKILL.md` — that file is the authoritative process description; this file only covers things useful for editing the skill's own code.

## Architecture

The design principle: **research is done by the LLM (or subagents), all arithmetic and HTML/email generation is done by the Python scripts.** Never hand-compute a percentage or hand-write the report HTML — that's what produces the "every number traces to a tool call" guarantee the skill promises.

Pipeline, per run (`WORK_DIR = drawdown-<YYYY-MM-DD>/`):

1. **Research (one subagent per ticker, parallel).** Each follows `references/worker_brief.md` with `{TICKER}/{WORK_DIR}/{SKILL_DIR}/{TODAY}` filled in. A worker fetches daily OHLC from a market-data tool, saves `<T>_daily.csv` (`date,open,high,low,close[,volume]`), and writes a narrative `<T>.json` conforming to `references/schema.md`.
2. **Compute** (`scripts/compute_drawdown.py`): reads `<T>_daily.csv` → writes `<T>_metrics.json` (52w high/low, % drop, trading days since high, 1m/3m/YTD/1y returns) and `<T>_weekly.csv` (weekly closes, used for the chart). The worker copies these numbers into `<T>.json`.
3. **Verify** (`scripts/verify.py`): independently re-derives the same metrics straight from each `<T>_daily.csv` and diffs them against `<T>.json` (tolerance `0.01`). Flags `MISSING`/`MISMATCH`/`NO SOURCE/TS` (hard failures, exit 1) vs `UNCITED`/`NO CROSS-CHECK` (warnings only). Writes `verified.json` — the numbers `build_report.py` actually displays, so a worker cannot inject a wrong headline number even if its JSON is wrong.
4. **Build** (`scripts/build_report.py`): combines `verified.json` (numbers) with each `<T>.json` (narrative, sources, holdings) and `<T>_weekly.csv` (chart) into one self-contained HTML file, inlining `assets/report.css`. The file is saved to `$WORK_DIR/drawdown_report.html` and presented to the user from there — it is never published with the Artifact tool or uploaded anywhere. Never hand-edit the generated HTML; page-wide changes belong in this script or the CSS.
5. **Email (optional, only if the user supplied an address)** (`scripts/build_email.py`): rebuilds an email-safe version from the same `verified.json`/`<T>.json` (inline styles, no `<style>`/SVG/web fonts, since email clients strip those) and writes a ready-to-send `.eml` with the HTML report attached. `scripts/send_email.py` is handed to the *user* to run on their own machine over SMTP with their own app password — Claude never sends email or touches credentials itself.

### Key invariant

`verify.py`'s recomputed numbers (`verified.json`), not the worker's self-reported numbers, are what `build_report.py` and `build_email.py` render. When editing any script, preserve this separation: a worker/subagent can get facts and narrative wrong and that's just a data gap, but it must never be able to make the published headline price/drawdown numbers wrong.

### File roles

| Path | Role |
|---|---|
| `SKILL.md` | the process the orchestrating Claude follows end-to-end — read this first for workflow questions |
| `references/worker_brief.md` | prompt template given to each per-ticker research subagent |
| `references/schema.md` | the `<TICKER>.json` contract that workers must produce and `verify.py`/`build_report.py` consume |
| `defaults.json` | default watchlist used when the user names no tickers (user-editable) |
| `examples/run-2026-10-16/` | a real reference run — use its JSONs for expected narrative depth/tone, and its `report.html` for expected output shape |
| `assets/report.css` | the HTML report's styling (light/dark via `prefers-color-scheme` and `data-theme`) |

## Running the scripts directly

All scripts are standalone, stdlib-only Python 3 (no `requirements.txt`, no venv needed).

```bash
# 1. compute metrics for one ticker from a saved daily CSV
python3 scripts/compute_drawdown.py --ticker SMH --daily work/SMH_daily.csv --out-dir work

# 2. verify all tickers in a work dir against their daily CSVs (exit 1 on problems)
python3 scripts/verify.py --dir work --tickers FTEC QQQ SMH ARTY

# 3. build the HTML report
python3 scripts/build_report.py --dir work --tickers FTEC QQQ SMH ARTY \
  --out work/drawdown_report.html --title "Tech ETF Drawdowns" --eyebrow "Drawdown review"

# 4. (optional) build a ready-to-send email from the same verified numbers
python3 scripts/build_email.py --dir work --tickers FTEC QQQ SMH ARTY \
  --to someone@example.com --report work/drawdown_report.html --title "Tech ETF Drawdowns"
```

There is no test suite; `scripts/verify.py` *is* the correctness check for a given run — run it against `examples/run-2026-10-16/` (copy the example JSONs/CSVs into a scratch work dir) to sanity-check changes to `compute_drawdown.py` or `verify.py` without doing live research.

## Editing conventions specific to this skill

- Treat `instrument_type` (`etf` | `stock` | `index`) as load-bearing: `is_index()` in both `build_report.py` and `build_email.py` switches formatting between `$` dollars and plain index points. An index ticker (e.g. SPX, DJI) is tracked at the index level, not via its proxy ETF, unless no index data source covers a full year.
- Percentages in `<TICKER>.json` and the metrics files are already in percent units (`-9.0979` means −9.10%), not fractions — don't re-divide by 100.
- `drivers`, `bull_case`, and `bear_case` items are expected to carry a `url` or `source_title`; `verify.py` only warns (`UNCITED`) rather than failing on this, but `build_report.py`'s `case_list()`/driver renderers assume the shape in `references/schema.md`.
- The skill is explicitly **read-only and non-advisory**: no order/alert/watchlist/trade tool calls anywhere in this pipeline, and the report must present bull and bear cases without a buy/sell recommendation. Keep any script or prompt changes consistent with that.
