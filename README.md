# DhanHQ Nifty Scalping Engine

A modular, paper-first Python engine for experimenting with Nifty 50 futures
and options strategies. The engine separates market data, signal generation,
cost calculation, execution, and journal analytics so the same strategy can
be evaluated in paper mode before any live order path is enabled.

## Safety defaults

- `EXECUTION_MODE=PAPER` is the default.
- In paper mode, DhanHQ market data is attempted first and yfinance is used
  automatically if DhanHQ is unavailable or times out.
- Set `PAPER_DATA_SOURCE=YFINANCE` to use Yahoo Finance directly, or
  `PAPER_DATA_SOURCE=DEMO` for the deterministic offline smoke feed.
- Live mode requires `DHAN_CLIENT_ID`, `DHAN_ACCESS_TOKEN`, and
  `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK`.
- Credentials must be stored as Replit Secrets. Never commit them to source
  control or paste them into chat.
- Tax and exchange rates are environment-configurable. Verify the current
  Dhan/NSE/government rate card before live use.

## Modules

- `config.py` — typed environment configuration and live safety gates
- `dhan_client.py` — async REST order wrapper and binary websocket adapter
- `cost_calculator.py` — brokerage, GST, STT, exchange, SEBI, stamp, and net P&L
- `scalp_strategy.py` — 5-second candles, EMA 5/13, VWAP, volume spikes,
  ATR trailing stop, target, and max-hold exits
- `execution_engine.py` — common order interface, realistic paper fills, live Dhan adapter
- `journal.py` — SQLite tick/execution/trade lifecycle journal and analytics
- `main.py` — async paper demo and guarded live entry point
- `market_data.py` — DhanHQ paper feed with yfinance fallback and offline demo feed

## Run the paper demo

```bash
python -m dhan_scalper.main
```

To configure a live market-data subscription, set
`DHAN_SUBSCRIPTIONS=NSE_FNO:security_id` (comma-separated for multiple
instruments). The live runner refuses to start when this is missing.

The default yfinance symbol is `^NSEI`, which is an index reference feed. It
is suitable for paper strategy plumbing and index-reference testing, but it
is not an options-premium feed and must not be treated as a replacement for
live option contract data.

For live dependencies:

```bash
pip install -e '.[live]'
```

The current live entry point intentionally stops before subscriptions are
started until an instrument subscription/configuration is supplied. This
prevents accidentally routing orders for an unspecified contract.