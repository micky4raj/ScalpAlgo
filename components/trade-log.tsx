'use client'

import type { Trade } from '@/lib/db/schema'
import { formatMoney } from '@/lib/market'
import { cn } from '@/lib/utils'

function timeAgo(date: Date | string) {
  const d = typeof date === 'string' ? new Date(date) : date
  const secs = Math.floor((Date.now() - d.getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.floor(hrs / 24)}d`
}

export function TradeLog({ trades }: { trades: Trade[] }) {
  const closed = trades.filter((t) => t.status === 'closed').slice(0, 20)

  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Trade Log</h2>
        <p className="text-xs text-muted-foreground">Recently closed scalps</p>
      </div>

      {closed.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-muted-foreground">
          No closed trades yet.
        </p>
      ) : (
        <ul className="divide-y divide-border/60">
          {closed.map((t) => {
            const pnl = t.pnl ?? 0
            return (
              <li key={t.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold">
                      {t.symbol}
                    </span>
                    <span
                      className={cn(
                        'rounded px-1 py-0.5 font-mono text-[10px] font-medium uppercase',
                        t.side === 'long'
                          ? 'bg-profit/10 text-profit'
                          : 'bg-loss/10 text-loss',
                      )}
                    >
                      {t.side}
                    </span>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {t.signalReason ?? 'manual'}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={cn(
                      'font-mono text-sm font-medium tabular-nums',
                      pnl > 0
                        ? 'text-profit'
                        : pnl < 0
                          ? 'text-loss'
                          : 'text-foreground',
                    )}
                  >
                    {pnl >= 0 ? '+' : '-'}
                    {formatMoney(Math.abs(pnl))}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {t.closedAt ? `${timeAgo(t.closedAt)} ago` : ''}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
