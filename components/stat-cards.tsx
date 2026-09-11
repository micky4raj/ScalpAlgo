'use client'

import { formatMoney } from '@/lib/market'
import { cn } from '@/lib/utils'

function pnlClass(n: number) {
  if (n > 0) return 'text-profit'
  if (n < 0) return 'text-loss'
  return 'text-foreground'
}

function signed(n: number) {
  const s = formatMoney(Math.abs(n))
  return n < 0 ? `-${s}` : `+${s}`
}

export function StatCards({
  equity,
  startingBalance,
  cash,
  realizedPnl,
  unrealizedPnl,
  openCount,
}: {
  equity: number
  startingBalance: number
  cash: number
  realizedPnl: number
  unrealizedPnl: number
  openCount: number
}) {
  const totalReturn = equity - startingBalance
  const returnPct = (totalReturn / startingBalance) * 100

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground">Account Equity</p>
        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
          {formatMoney(equity)}
        </p>
        <p className={cn('mt-1 font-mono text-xs', pnlClass(totalReturn))}>
          {signed(totalReturn)} ({returnPct >= 0 ? '+' : ''}
          {returnPct.toFixed(2)}%)
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground">Buying Power</p>
        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums">
          {formatMoney(cash)}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">available cash</p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground">Realized P&amp;L</p>
        <p
          className={cn(
            'mt-1 font-mono text-2xl font-semibold tabular-nums',
            pnlClass(realizedPnl),
          )}
        >
          {signed(realizedPnl)}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">closed trades</p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground">Open P&amp;L</p>
        <p
          className={cn(
            'mt-1 font-mono text-2xl font-semibold tabular-nums',
            pnlClass(unrealizedPnl),
          )}
        >
          {signed(unrealizedPnl)}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {openCount} open position{openCount === 1 ? '' : 's'}
        </p>
      </div>
    </div>
  )
}
