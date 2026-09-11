'use client'

import { FAST_EMA, SLOW_EMA, STOP_LOSS, TAKE_PROFIT } from '@/lib/market'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

export function AlgoPanel({
  algoOn,
  onToggle,
  onReset,
  disabled,
}: {
  algoOn: boolean
  onToggle: () => void
  onReset: () => void
  disabled: boolean
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Scalping Algorithm</h2>
        <p className="text-xs text-muted-foreground">
          EMA crossover + RSI momentum
        </p>
      </div>

      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-center justify-between rounded-md border border-border bg-background px-3 py-2.5">
          <div>
            <Label htmlFor="algo-switch" className="text-sm font-medium">
              Auto-trade
            </Label>
            <p className="text-xs text-muted-foreground">
              {algoOn ? 'Scanning every tick' : 'Currently paused'}
            </p>
          </div>
          <Switch
            id="algo-switch"
            checked={algoOn}
            onCheckedChange={onToggle}
            disabled={disabled}
          />
        </div>

        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <dt className="text-muted-foreground">Fast / Slow EMA</dt>
            <dd className="mt-0.5 font-mono font-medium tabular-nums">
              {FAST_EMA} / {SLOW_EMA}
            </dd>
          </div>
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <dt className="text-muted-foreground">Take profit</dt>
            <dd className="mt-0.5 font-mono font-medium text-profit tabular-nums">
              +{(TAKE_PROFIT * 100).toFixed(2)}%
            </dd>
          </div>
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <dt className="text-muted-foreground">Stop loss</dt>
            <dd className="mt-0.5 font-mono font-medium text-loss tabular-nums">
              -{(STOP_LOSS * 100).toFixed(2)}%
            </dd>
          </div>
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <dt className="text-muted-foreground">Size / scalp</dt>
            <dd className="mt-0.5 font-mono font-medium tabular-nums">
              $5,000
            </dd>
          </div>
        </dl>

        <Button
          variant="outline"
          size="sm"
          onClick={onReset}
          disabled={disabled}
          className="w-full"
        >
          Reset portfolio
        </Button>
      </div>
    </section>
  )
}
