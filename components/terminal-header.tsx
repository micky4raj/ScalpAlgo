'use client'

import { Activity } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function TerminalHeader({
  userName,
  algoOn,
  onSignOut,
}: {
  userName: string
  algoOn: boolean
  onSignOut: () => void
}) {
  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Activity className="h-4.5 w-4.5" aria-hidden="true" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-mono text-sm font-semibold tracking-tight">
              scalpr
            </span>
            <span className="text-[11px] text-muted-foreground">
              paper terminal
            </span>
          </div>
          <span
            className={`ml-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
              algoOn
                ? 'border-profit/30 bg-profit/10 text-profit'
                : 'border-border bg-muted text-muted-foreground'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                algoOn ? 'bg-profit animate-pulse' : 'bg-muted-foreground'
              }`}
              aria-hidden="true"
            />
            {algoOn ? 'ALGO LIVE' : 'ALGO IDLE'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {userName}
          </span>
          <Button variant="outline" size="sm" onClick={onSignOut}>
            Sign out
          </Button>
        </div>
      </div>
    </header>
  )
}
