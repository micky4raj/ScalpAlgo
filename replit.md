# DhanHQ Nifty Scalping Engine

Paper-first async Python engine for evaluating Nifty 50 futures and options
scalping strategies with DhanHQ adapters, transparent trading costs, and a
SQLite trade journal.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- `python -m dhan_scalper.main` — run the safe paper-mode demonstration
- Install optional live dependencies with `pip install -e '.[live]'`
- Paper market data tries DhanHQ first, then falls back to yfinance; use
  `PAPER_DATA_SOURCE=DEMO` for offline smoke checks

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)
- Trading engine: Python 3.11+, asyncio, optional uvloop/aiohttp/websockets,
  SQLite

## Where things live

- `dhan_scalper/` — modular trading engine
- `dhan_scalper/config.py` — environment-driven source of truth for safety,
  strategy, risk, and cost settings
- `README.md` and `.env.example` — setup and operational guardrails

## Architecture decisions

- Paper mode is the default and has no network dependency.
- Live mode requires both Dhan credentials and an explicit confirmation string.
- Strategy code depends on `Tick` and `Signal`, not on broker transport.
- Costs are configurable rather than hard-coded as permanently current rates.
- SQLite stores the full local execution lifecycle and analytics inputs.

## Product

The engine supports paper evaluation of Nifty scalping signals, net-of-cost P&L
calculation, execution latency/slippage logging, and a guarded DhanHQ live
adapter for a specifically configured instrument.

## User preferences

No additional preferences recorded.

## Gotchas

- Never enable live mode without confirming current DhanHQ/NSE rate-card values.
- Do not put Dhan credentials in `.env.example`, source control, or chat.
- The live runner refuses to start without a configured instrument subscription.
- yfinance `^NSEI` is index data and is not an options-premium substitute.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
