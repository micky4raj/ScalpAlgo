'use client'

import type { Trade } from '@/lib/db/schema'
import { type Symbol, formatMoney, formatPrice, unrealized } from '@/lib/market'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Live = Record<Symbol, { price: number; prev: number; history: number[] }>

export function PositionsTable({
  positions,
  live,
  onClose,
  disabled,
}: {
  positions: Trade[]
  live: Live
  onClose: (id: number, symbol: string) => void
  disabled: boolean
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Open Positions</h2>
        <p className="text-xs text-muted-foreground">
          Live mark-to-market P&amp;L
        </p>
      </div>

      {positions.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-muted-foreground">
          No open positions. Enable the algorithm or trade manually.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Side</th>
                <th className="px-4 py-2 text-right font-medium">Entry</th>
                <th className="px-4 py-2 text-right font-medium">Mark</th>
                <th className="px-4 py-2 text-right font-medium">P&amp;L</th>
                <th className="px-4 py-2 text-right font-medium sr-only">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => {
                const l = live[pos.symbol as Symbol]
                const mark = l?.price ?? pos.entryPrice
                const pnl = unrealized(
                  pos.side as 'long' | 'short',
                  pos.entryPrice,
                  mark,
                  pos.qty,
                )
                return (
                  <tr
                    key={pos.id}
                    className="border-b border-border/60 last:border-0"
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-mono font-semibold">
                        {pos.symbol}
                      </span>
                      <span className="ml-2 text-xs text-muted-foreground tabular-nums">
                        {pos.qty}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 font-mono text-xs font-medium uppercase',
                          pos.side === 'long'
                            ? 'bg-profit/10 text-profit'
                            : 'bg-loss/10 text-loss',
                        )}
                      >
                        {pos.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                      {formatPrice(pos.entryPrice)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                      {formatPrice(mark)}
                    </td>
                    <td
                      className={cn(
                        'px-4 py-2.5 text-right font-mono font-medium tabular-nums',
                        pnl > 0
                          ? 'text-profit'
                          : pnl < 0
                            ? 'text-loss'
                            : 'text-foreground',
                      )}
                    >
                      {pnl >= 0 ? '+' : '-'}
                      {formatMoney(Math.abs(pnl)).replace('$', '$')}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        disabled={disabled}
                        onClick={() => onClose(pos.id, pos.symbol)}
                      >
                        Close
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
