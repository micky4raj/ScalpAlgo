// Simulated market feed + scalping algorithm. All pure/stateless helpers so
// the same logic can drive the live client loop deterministically.

export type Symbol = 'BTC' | 'ETH' | 'SOL' | 'NVDA'

export interface Instrument {
  symbol: Symbol
  name: string
  price: number
  vol: number // per-tick volatility as a fraction of price
}

export const INSTRUMENTS: Instrument[] = [
  { symbol: 'BTC', name: 'Bitcoin', price: 68000, vol: 0.0009 },
  { symbol: 'ETH', name: 'Ethereum', price: 3600, vol: 0.0012 },
  { symbol: 'SOL', name: 'Solana', price: 172, vol: 0.0018 },
  { symbol: 'NVDA', name: 'NVIDIA', price: 122, vol: 0.0011 },
]

// Random walk with mild mean-reverting drift so prices stay in a believable band.
export function nextPrice(inst: Instrument): number {
  const shock = (Math.random() - 0.5) * 2 * inst.vol
  const drift = (Math.random() - 0.5) * inst.vol * 0.4
  const next = inst.price * (1 + shock + drift)
  return Math.max(next, 0.01)
}

// Exponential moving average over the most recent `period` samples.
export function ema(values: number[], period: number): number {
  if (values.length === 0) return 0
  const k = 2 / (period + 1)
  let e = values[0]
  for (let i = 1; i < values.length; i++) {
    e = values[i] * k + e * (1 - k)
  }
  return e
}

// Simple RSI over the provided price series.
export function rsi(values: number[], period = 14): number {
  if (values.length < period + 1) return 50
  let gains = 0
  let losses = 0
  for (let i = values.length - period; i < values.length; i++) {
    const diff = values[i] - values[i - 1]
    if (diff >= 0) gains += diff
    else losses -= diff
  }
  if (losses === 0) return 100
  const rs = gains / losses
  return 100 - 100 / (1 + rs)
}

export const FAST_EMA = 5
export const SLOW_EMA = 20
export const TAKE_PROFIT = 0.0025 // +0.25%
export const STOP_LOSS = 0.0015 // -0.15%

export interface EntrySignal {
  side: 'long' | 'short'
  reason: string
}

// Decide whether to open a new scalp. Momentum (fast vs slow EMA) confirmed by RSI.
export function entrySignal(history: number[]): EntrySignal | null {
  if (history.length < SLOW_EMA + 1) return null
  const fast = ema(history.slice(-FAST_EMA * 2), FAST_EMA)
  const slow = ema(history.slice(-SLOW_EMA * 2), SLOW_EMA)
  const strength = rsi(history)
  const spread = (fast - slow) / slow

  if (spread > 0.0008 && strength < 70) {
    return { side: 'long', reason: `EMA${FAST_EMA}>EMA${SLOW_EMA} · RSI ${strength.toFixed(0)}` }
  }
  if (spread < -0.0008 && strength > 30) {
    return { side: 'short', reason: `EMA${FAST_EMA}<EMA${SLOW_EMA} · RSI ${strength.toFixed(0)}` }
  }
  return null
}

// Decide whether to close an open scalp given the live price.
export function exitSignal(
  side: 'long' | 'short',
  entryPrice: number,
  currentPrice: number,
): string | null {
  const change = (currentPrice - entryPrice) / entryPrice
  const signed = side === 'long' ? change : -change
  if (signed >= TAKE_PROFIT) return 'take-profit'
  if (signed <= -STOP_LOSS) return 'stop-loss'
  return null
}

export function unrealized(
  side: 'long' | 'short',
  entryPrice: number,
  currentPrice: number,
  qty: number,
): number {
  const diff = side === 'long' ? currentPrice - entryPrice : entryPrice - currentPrice
  return diff * qty
}

export function formatMoney(n: number): string {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function formatPrice(n: number): string {
  return n.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
