'use client'

import { INSTRUMENTS, type Symbol, formatPrice } from '@/lib/market'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ArrowDown, ArrowUp } from 'lucide-react'

type Live = Record<Symbol, { price: number; prev: number; history: number[] }>

function Sparkline({ history }: { history: number[] }) {
  if (history.length < 2) return null
  const min = Math.min(...history)
  const max = Math.max(...history)
  const range = max - min || 1
  const w = 100
  const h = 28
  const pts = history
    .map((v, i) => {
      const x = (i / (history.length - 1)) * w
      const y = h - ((v - min) / range) * h
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const up = history[history.length - 1] >= history[0]
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-7 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline
        points={pts}
        fill="none"
        stroke={up ? 'var(--profit)' : 'var(--loss)'}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export function MarketTicker({
  live,
  onTrade,
  disabled,
}: {
  live: Live
  onTrade: (symbol: Symbol, side: 'long' | 'short') => void
  disabled: boolean
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Live Markets</h2>
        <p className="text-xs text-muted-foreground">
          Simulated feed · updates every 1.2s
        </p>
      </div>
      <div className="divide-y divide-border">
        {INSTRUMENTS.map((inst) => {
          const l = live[inst.symbol]
          const change = ((l.price - l.prev) / l.prev) * 100
          const up = l.price >= l.prev
          return (
            <div
              key={inst.symbol}
              className="flex items-center gap-3 px-4 py-3"
            >
              <div className="w-24 shrink-0">
                <p className="font-mono text-sm font-semibold">
                  {inst.symbol}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {inst.name}
                </p>
              </div>

              <div className="hidden flex-1 sm:block">
                <Sparkline history={l.history} />
              </div>

              <div className="w-28 shrink-0 text-right">
                <p className="font-mono text-sm font-semibold tabular-nums">
                  {formatPrice(l.price)}
                </p>
                <p
                  className={cn(
                    'flex items-center justify-end gap-0.5 font-mono text-xs tabular-nums',
                    up ? 'text-profit' : 'text-loss',
                  )}
                >
                  {up ? (
                    <ArrowUp className="h-3 w-3" aria-hidden="true" />
                  ) : (
                    <ArrowDown className="h-3 w-3" aria-hidden="true" />
                  )}
                  {Math.abs(change).toFixed(2)}%
                </p>
              </div>

              <div className="flex shrink-0 gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-profit/40 px-2.5 text-profit hover:bg-profit/10 hover:text-profit"
                  disabled={disabled}
                  onClick={() => onTrade(inst.symbol, 'long')}
                >
                  Buy
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 border-loss/40 px-2.5 text-loss hover:bg-loss/10 hover:text-loss"
                  disabled={disabled}
                  onClick={() => onTrade(inst.symbol, 'short')}
                >
                  Sell
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
