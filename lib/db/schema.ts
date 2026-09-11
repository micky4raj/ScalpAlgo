import {
  boolean,
  numeric,
  pgTable,
  serial,
  text,
  timestamp,
} from 'drizzle-orm/pg-core'

// ---- Better Auth tables (do not rename columns) ----

export const user = pgTable('user', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  emailVerified: boolean('emailVerified').notNull().default(false),
  image: text('image'),
  createdAt: timestamp('createdAt').notNull().defaultNow(),
  updatedAt: timestamp('updatedAt').notNull().defaultNow(),
})

export const session = pgTable('session', {
  id: text('id').primaryKey(),
  expiresAt: timestamp('expiresAt').notNull(),
  token: text('token').notNull().unique(),
  createdAt: timestamp('createdAt').notNull().defaultNow(),
  updatedAt: timestamp('updatedAt').notNull().defaultNow(),
  ipAddress: text('ipAddress'),
  userAgent: text('userAgent'),
  userId: text('userId')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
})

export const account = pgTable('account', {
  id: text('id').primaryKey(),
  accountId: text('accountId').notNull(),
  providerId: text('providerId').notNull(),
  userId: text('userId')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  accessToken: text('accessToken'),
  refreshToken: text('refreshToken'),
  idToken: text('idToken'),
  accessTokenExpiresAt: timestamp('accessTokenExpiresAt'),
  refreshTokenExpiresAt: timestamp('refreshTokenExpiresAt'),
  scope: text('scope'),
  password: text('password'),
  createdAt: timestamp('createdAt').notNull().defaultNow(),
  updatedAt: timestamp('updatedAt').notNull().defaultNow(),
})

export const verification = pgTable('verification', {
  id: text('id').primaryKey(),
  identifier: text('identifier').notNull(),
  value: text('value').notNull(),
  expiresAt: timestamp('expiresAt').notNull(),
  createdAt: timestamp('createdAt').notNull().defaultNow(),
  updatedAt: timestamp('updatedAt').notNull().defaultNow(),
})

// ---- App tables ----

export const portfolios = pgTable('portfolios', {
  id: serial('id').primaryKey(),
  userId: text('userId').notNull(),
  startingBalance: numeric('startingBalance', { mode: 'number' })
    .notNull()
    .default(100000),
  cash: numeric('cash', { mode: 'number' }).notNull().default(100000),
  realizedPnl: numeric('realizedPnl', { mode: 'number' }).notNull().default(0),
  algoEnabled: boolean('algoEnabled').notNull().default(false),
  createdAt: timestamp('createdAt').notNull().defaultNow(),
  updatedAt: timestamp('updatedAt').notNull().defaultNow(),
})

export const trades = pgTable('trades', {
  id: serial('id').primaryKey(),
  userId: text('userId').notNull(),
  symbol: text('symbol').notNull(),
  side: text('side').notNull(), // 'long' | 'short'
  qty: numeric('qty', { mode: 'number' }).notNull(),
  entryPrice: numeric('entryPrice', { mode: 'number' }).notNull(),
  exitPrice: numeric('exitPrice', { mode: 'number' }),
  pnl: numeric('pnl', { mode: 'number' }),
  status: text('status').notNull().default('open'), // 'open' | 'closed'
  signalReason: text('signalReason'),
  openedAt: timestamp('openedAt').notNull().defaultNow(),
  closedAt: timestamp('closedAt'),
})

export type Portfolio = typeof portfolios.$inferSelect
export type Trade = typeof trades.$inferSelect
