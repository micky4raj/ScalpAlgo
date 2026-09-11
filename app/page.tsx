import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { getPortfolio, getTrades } from '@/app/actions/trading'
import { TradingTerminal } from '@/components/trading-terminal'

export default async function Home() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session?.user) redirect('/sign-in')

  const [portfolio, trades] = await Promise.all([getPortfolio(), getTrades()])

  return (
    <TradingTerminal
      userName={session.user.name || session.user.email}
      initialPortfolio={portfolio}
      initialTrades={trades}
    />
  )
}
