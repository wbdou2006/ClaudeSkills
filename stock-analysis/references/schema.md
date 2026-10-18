# `<TICKER>.json` — the worker output contract

`build_report.py` reads exactly these fields, and `verify.py` checks them. Missing optional fields render as "No data". Missing required fields (marked **R**) fail verification.

**Where the numbers come from:**
- The price numbers must equal `<TICKER>_metrics.json`, which comes from `compute_drawdown.py`.
- Percentages are in percent units: `-9.0979` means −9.10%.
- The expense ratio is also in percent: `0.35` means 0.35%.

```json
{
  "ticker": "SMH",                                   // R
  "instrument_type": "etf",                          // etf | stock | index. "index" shows prices as points, not $
  "fund_name": "VanEck Semiconductor ETF",           // R. Any text after " (" is dropped from headings
  "issuer": "VanEck",
  "index_tracked": "MVIS US Listed Semiconductor 25 Index",
  "expense_ratio": {"value": 0.35, "source": "", "retrieved_at": ""},

  "last_trading_date": "2026-10-16",                 // R
  "current_price":     {"value": 539.79, "basis": "official close", "date": "2026-10-16",
                        "source": "tool name / URL", "retrieved_at": "2026-10-18T20:22:23Z"},   // R, source + retrieved_at required
  "high_52w_intraday": {"value": 671.83, "date": "2026-06-22", "source": "", "retrieved_at": ""}, // R, source + retrieved_at required
  "high_52w_close":    {"value": 668.91, "date": "2026-06-22"},
  "low_52w_intraday":  {"value": 315.05, "date": "2025-11-21"},
  "drop_pct_from_intraday_high": -19.6538,           // R
  "drop_pct_from_closing_high": -19.303,
  "drop_dollars": -132.04,
  "trading_days_since_high": 82,
  "returns_pct": {"1m": -3.71, "3m": -3.41, "ytd": 49.89, "1y": 57.24},

  "cross_check": {"source": "", "retrieved_at": "", "price": 539.62, "high_52w": 671.83, "note": ""},

  "top_holdings": [{"name": "NVIDIA Corp", "symbol": "NVDA", "weight_pct": 20.06}],
  "holdings_source": "VanEck holdings page",
  "holdings_as_of": "2026-10-15",

  "drop_summary": "2-3 plain-English sentences: when the high was, how far it fell, the main reason.",  // R
  "drivers": [                                        // R. Ordered by importance, each dated and cited
    {"driver": "Short headline", "detail": "What happened, with numbers from tools",
     "date": "2026-06-23", "source_title": "Outlet - headline (date)", "url": "https://..."}
  ],
  "bull_case": [{"point": "Short claim", "evidence": "Cited fact", "source_title": "", "url": ""}],  // R, 3-5 items
  "bear_case": [{"point": "Short claim", "evidence": "Cited fact", "source_title": "", "url": ""}],  // R, 3-5 items
  "data_gaps": ["What was unavailable and what was used instead"],                                  // R (may be [])
  "calc_output": "verbatim stdout of compute_drawdown.py"
}
```

**Rules for each section:**
- **`drivers`, `bull_case`, `bear_case`:** every item needs a `url` or a `source_title`. `verify.py` flags items that have neither.
- **`data_gaps`:** list every tool that failed, every conflict between sources, and every value you could not fetch. These appear in the report's "Data gaps" panel.
