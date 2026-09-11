'use server'

import { auth } from '@/lib/auth'
import { db } from '@/lib/db'
import { portfolios, trades } from '@/lib/db/schema'
import { and, desc, eq } from 'drizzle-orm'
import { headers } from 'next/headers'
import { revalidatePath } from 'next/cache'

const STARTING_BALANCE = 100000
const MAX_QTY_NOTIONAL = 25000 // max $ per position, enforced server-side

async function getUserId() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session?.user) throw new Error('Unauthorized')
  return session.user.id
}

export async function getPortfolio() {
  const userId = await getUserId()
  const existing = await db
    .select()
    .from(portfolios)
    .where(eq(portfolios.userId, userId))
    .limit(1)

  if (existing.length > 0) return existing[0]

  const [created] = await db
    .insert(portfolios)
    .values({
      userId,
      startingBalance: STARTING_BALANCE,
      cash: STARTING_BALANCE,
      realizedPnl: 0,
      algoEnabled: false,
    })
    .returning()
  return created
}

export async function getTrades() {
  const userId = await getUserId()
  return db
    .select()
    .from(trades)
    .where(eq(trades.userId, userId))
    .orderBy(desc(trades.openedAt))
    .limit(100)
}

export async function setAlgoEnabled(enabled: boolean) {
  const userId = await getUserId()
  await db
    .update(portfolios)
    .set({ algoEnabled: enabled, updatedAt: new Date() })
    .where(eq(portfolios.userId, userId))
  revalidatePath('/')
}

export async function openTrade(input: {
  symbol: string
  side: 'long' | 'short'
  qty: number
  entryPrice: number
  signalReason?: string
}) {
  const userId = await getUserId()

  // Server-side validation — never trust client-supplied qty/price.
  const entryPrice = Number(input.entryPrice)
  const qty = Number(input.qty)
  if (!Number.isFinite(entryPrice) || entryPrice <= 0) throw new Error('Bad price')
  if (!Number.isFinite(qty) || qty <= 0) throw new Error('Bad quantity')
  if (input.side !== 'long' && input.side !== 'short') throw new Error('Bad side')

  let notional = entryPrice * qty
  if (notional > MAX_QTY_NOTIONAL) {
    return { ok: false as const, error: 'Position exceeds $25,000 limit' }
  }

  const portfolio = await getPortfolio()
  if (notional > portfolio.cash) {
    return { ok: false as const, error: 'Insufficient buying power' }
  }

  await db.transaction(async (tx) => {
    await tx.insert(trades).values({
      userId,
      symbol: input.symbol,
      side: input.side,
      qty,
      entryPrice,
      status: 'open',
      signalReason: input.signalReason ?? null,
    })
    await tx
      .update(portfolios)
      .set({ cash: portfolio.cash - notional, updatedAt: new Date() })
      .where(eq(portfolios.userId, userId))
  })

  revalidatePath('/')
  return { ok: true as const }
}

export async function closeTrade(input: { id: number; exitPrice: number }) {
  const userId = await getUserId()
  const exitPrice = Number(input.exitPrice)
  if (!Number.isFinite(exitPrice) || exitPrice <= 0) throw new Error('Bad price')

  const [trade] = await db
    .select()
    .from(trades)
    .where(and(eq(trades.id, input.id), eq(trades.userId, userId)))
    .limit(1)

  if (!trade || trade.status !== 'open') {
    return { ok: false as const, error: 'Trade not open' }
  }

  const diff =
    trade.side === 'long'
      ? exitPrice - trade.entryPrice
      : trade.entryPrice - exitPrice
  const pnl = diff * trade.qty
  const reserved = trade.entryPrice * trade.qty

  const portfolio = await getPortfolio()

  await db.transaction(async (tx) => {
    await tx
      .update(trades)
      .set({ exitPrice, pnl, status: 'closed', closedAt: new Date() })
      .where(and(eq(trades.id, input.id), eq(trades.userId, userId)))
    await tx
      .update(portfolios)
      .set({
        cash: portfolio.cash + reserved + pnl,
        realizedPnl: portfolio.realizedPnl + pnl,
        updatedAt: new Date(),
      })
      .where(eq(portfolios.userId, userId))
  })

  revalidatePath('/')
  return { ok: true as const, pnl }
}

export async function resetPortfolio() {
  const userId = await getUserId()
  await db.transaction(async (tx) => {
    await tx.delete(trades).where(eq(trades.userId, userId))
    await tx
      .update(portfolios)
      .set({
        cash: STARTING_BALANCE,
        realizedPnl: 0,
        algoEnabled: false,
        updatedAt: new Date(),
      })
      .where(eq(portfolios.userId, userId))
  })
  revalidatePath('/')
}
