'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  INSTRUMENTS,
  type Instrument,
  type Symbol,
  entrySignal,
  exitSignal,
  formatMoney,
  nextPrice,
  unrealized,
} from '@/lib/market'
import type { Portfolio, Trade } from '@/lib/db/schema'
import {
  closeTrade,
  getPortfolio,
  getTrades,
  openTrade,
  resetPortfolio,
  setAlgoEnabled,
} from '@/app/actions/trading'
import { signOut } from '@/lib/auth-client'
import { TerminalHeader } from '@/components/terminal-header'
import { StatCards } from '@/components/stat-cards'
import { MarketTicker } from '@/components/market-ticker'
import { PositionsTable } from '@/components/positions-table'
import { TradeLog } from '@/components/trade-log'
import { AlgoPanel } from '@/components/algo-panel'

const TICK_MS = 1200
const HISTORY_LEN = 60
const ALGO_QTY_NOTIONAL = 5000 // $ per algo scalp

type LiveState = Record<Symbol, { price: number; prev: number; history: number[] }>

function seedState(): LiveState {
  const state = {} as LiveState
  for (const inst of INSTRUMENTS) {
    state[inst.symbol] = {
      price: inst.price,
      prev: inst.price,
      history: [inst.price],
    }
  }
  return state
}

export function TradingTerminal({
  userName,
  initialPortfolio,
  initialTrades,
}: {
  userName: string
  initialPortfolio: Portfolio
  initialTrades: Trade[]
}) {
  const router = useRouter()
  const [live, setLive] = useState<LiveState>(seedState)
  const [portfolio, setPortfolio] = useState<Portfolio>(initialPortfolio)
  const [trades, setTrades] = useState<Trade[]>(initialTrades)
  const [algoOn, setAlgoOn] = useState(initialPortfolio.algoEnabled)
  const [busy, setBusy] = useState(false)

  // Refs the tick loop reads without re-subscribing.
  const liveRef = useRef(live)
  const tradesRef = useRef(trades)
  const algoRef = useRef(algoOn)
  const pendingRef = useRef(false)
  liveRef.current = live
  tradesRef.current = trades
  algoRef.current = algoOn

  const refresh = useCallback(async () => {
    const [p, t] = await Promise.all([getPortfolio(), getTrades()])
    setPortfolio(p)
    setTrades(t)
    setAlgoOn(p.algoEnabled)
  }, [])

  // Price feed — advances every symbol on an interval.
  useEffect(() => {
    const id = setInterval(() => {
      setLive((prev) => {
        const next = {} as LiveState
        for (const inst of INSTRUMENTS) {
          const cur = prev[inst.symbol]
          const price = nextPrice({ ...inst, price: cur.price } as Instrument)
          const history = [...cur.history, price].slice(-HISTORY_LEN)
          next[inst.symbol] = { price, prev: cur.price, history }
        }
        return next
      })
    }, TICK_MS)
    return () => clearInterval(id)
  }, [])

  // Algorithm loop — reacts to each new price frame.
  useEffect(() => {
    if (pendingRef.current) return
    const open = tradesRef.current.filter((t) => t.status === 'open')

    const run = async () => {
      pendingRef.current = true
      let changed = false
      try {
        // 1) Manage exits on all open positions.
        for (const pos of open) {
          const l = liveRef.current[pos.symbol as Symbol]
          if (!l) continue
          const reason = exitSignal(
            pos.side as 'long' | 'short',
            pos.entryPrice,
            l.price,
          )
          if (reason) {
            await closeTrade({ id: pos.id, exitPrice: l.price })
            changed = true
          }
        }

        // 2) Look for a new entry (algo only, one position per symbol).
        if (algoRef.current) {
          const held = new Set(open.map((t) => t.symbol))
          for (const inst of INSTRUMENTS) {
            if (held.has(inst.symbol)) continue
            const l = liveRef.current[inst.symbol]
            const sig = entrySignal(l.history)
            if (sig) {
              const qty = Number((ALGO_QTY_NOTIONAL / l.price).toFixed(4))
              const res = await openTrade({
                symbol: inst.symbol,
                side: sig.side,
                qty,
                entryPrice: l.price,
                signalReason: sig.reason,
              })
              if (res.ok) changed = true
              break // one new scalp per frame keeps risk in check
            }
          }
        }

        if (changed) await refresh()
      } finally {
        pendingRef.current = false
      }
    }

    void run()
  }, [live, refresh])

  const openPositions = trades.filter((t) => t.status === 'open')

  // Live equity = cash + reserved capital + unrealized P&L on open positions.
  let openValue = 0
  let openUnrealized = 0
  for (const pos of openPositions) {
    const l = live[pos.symbol as Symbol]
    if (!l) continue
    openValue += pos.entryPrice * pos.qty
    openUnrealized += unrealized(
      pos.side as 'long' | 'short',
      pos.entryPrice,
      l.price,
      pos.qty,
    )
  }
  const equity = portfolio.cash + openValue + openUnrealized

  const handleToggleAlgo = async () => {
    const next = !algoOn
    setAlgoOn(next)
    await setAlgoEnabled(next)
  }

  const handleManualClose = async (id: number, symbol: string) => {
    setBusy(true)
    const l = live[symbol as Symbol]
    await closeTrade({ id, exitPrice: l.price })
    await refresh()
    setBusy(false)
  }

  const handleManualTrade = async (
    symbol: Symbol,
    side: 'long' | 'short',
  ) => {
    setBusy(true)
    const l = live[symbol]
    const qty = Number((ALGO_QTY_NOTIONAL / l.price).toFixed(4))
    const res = await openTrade({
      symbol,
      side,
      qty,
      entryPrice: l.price,
      signalReason: 'manual',
    })
    if (res.ok) await refresh()
    setBusy(false)
  }

  const handleReset = async () => {
    setBusy(true)
    setAlgoOn(false)
    await resetPortfolio()
    await refresh()
    setBusy(false)
  }

  const handleSignOut = async () => {
    await signOut()
    router.push('/sign-in')
    router.refresh()
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <TerminalHeader
        userName={userName}
        algoOn={algoOn}
        onSignOut={handleSignOut}
      />

      <main className="mx-auto w-full max-w-6xl px-4 py-6 flex flex-col gap-6">
        <StatCards
          equity={equity}
          startingBalance={portfolio.startingBalance}
          cash={portfolio.cash}
          realizedPnl={portfolio.realizedPnl}
          unrealizedPnl={openUnrealized}
          openCount={openPositions.length}
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <MarketTicker
              live={live}
              onTrade={handleManualTrade}
              disabled={busy}
            />
            <PositionsTable
              positions={openPositions}
              live={live}
              onClose={handleManualClose}
              disabled={busy}
            />
          </div>

          <div className="flex flex-col gap-6">
            <AlgoPanel
              algoOn={algoOn}
              onToggle={handleToggleAlgo}
              onReset={handleReset}
              disabled={busy}
            />
            <TradeLog trades={trades} />
          </div>
        </div>
      </main>
    </div>
  )
}
