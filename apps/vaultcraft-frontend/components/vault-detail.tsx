"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Lock, Eye, TrendingUp, TrendingDown, ArrowUpRight, Wallet } from "lucide-react"
import { PerformanceChart } from "@/components/performance-chart"
import { DepositModal } from "@/components/deposit-modal"
import { useEffect, useMemo, useState } from "react"
import { getNav, getVault } from "@/lib/api"
import { useOnchainVault } from "@/hooks/use-onchain-vault"
import { ExecPanel } from "@/components/exec-panel"
import { EventsFeed } from "@/components/events-feed"

type UIState = {
  id: string
  name: string
  type: "public" | "private"
  aum: number
  sharpe: number
  annualReturn: number
  volatility: number
  maxDrawdown: number
  recoveryDays: number
  performanceFee: number
  managementFee: number
  lockDays: number
  managerStake: number
  unitNav: number
  totalShares: number
}

const fallbackVault: UIState = {
  id: "0x1234...5678",
  name: "Alpha Momentum Strategy",
  type: "public",
  aum: 4250000,
  sharpe: 2.34,
  annualReturn: 24.5,
  volatility: 12.3,
  maxDrawdown: -8.2,
  recoveryDays: 45,
  performanceFee: 10,
  managementFee: 0,
  lockDays: 1,
  managerStake: 8.5,
  unitNav: 1.245,
  totalShares: 3414634,
}

export function VaultDetail({ vaultId }: { vaultId: string }) {
  const [showDeposit, setShowDeposit] = useState(false)
  const [vault, setVault] = useState<UIState>(fallbackVault)
  const [navData, setNavData] = useState<number[]>([])
  const chain = useOnchainVault(vaultId)

  useEffect(() => {
    let alive = true
    getVault(vaultId)
      .then((v) => {
        if (!alive) return
        const ui: UIState = {
          id: v.id,
          name: v.name,
          type: v.type,
          aum: v.aum ?? 1_000_000,
          sharpe: v.metrics?.sharpe ?? 0,
          annualReturn: (v.metrics?.ann_return ?? 0) * 100,
          volatility: (v.metrics?.ann_vol ?? 0) * 100,
          maxDrawdown: (v.metrics?.mdd ?? 0) * 100,
          recoveryDays: v.metrics?.recovery_days ?? 0,
          performanceFee: v.performanceFee,
          managementFee: v.managementFee,
          lockDays: v.lockDays,
          managerStake: 10,
          unitNav: v.unitNav,
          totalShares: v.totalShares,
        }
        setVault(ui)
      })
      .catch(() => {})
    getNav(vaultId, 90)
      .then((series) => {
        if (!alive) return
        setNavData(series)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [vaultId])

  const chartPoints = useMemo(() => {
    const now = Date.now()
    return navData.map((v, i, arr) => ({
      date: new Date(now - (arr.length - 1 - i) * 24 * 60 * 60 * 1000).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      nav: v,
    }))
  }, [navData])

  return (
    <>
      <section className="py-12 border-b border-border/40">
        <div className="container mx-auto px-4">
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-4">
              <h1 className="text-3xl font-bold">{vault.name}</h1>
              <Badge variant="secondary" className="gap-1.5">
                {mockVault.type === "public" ? <Eye className="h-3 w-3" /> : <Lock className="h-3 w-3" />}
                <span className="capitalize">{mockVault.type}</span>
              </Badge>
            </div>
            <p className="text-muted-foreground font-mono text-sm">{vault.id}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <Card className="p-4 gradient-card border-border/40">
              <div className="text-sm text-muted-foreground mb-1">Total AUM</div>
              <div className="text-2xl font-bold font-mono">${(((chain.aum ?? vault.aum) as number) / 1_000_000).toFixed(2)}M</div>
            </Card>
            <Card className="p-4 gradient-card border-border/40">
              <div className="text-sm text-muted-foreground mb-1">Unit NAV</div>
              <div className="text-2xl font-bold font-mono">${(chain.unitNav ?? vault.unitNav).toFixed(3)}</div>
            </Card>
            <Card className="p-4 gradient-card border-border/40">
              <div className="text-sm text-muted-foreground mb-1">Annual Return</div>
              <div className="text-2xl font-bold text-success flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                {vault.annualReturn.toFixed(1)}%
              </div>
            </Card>
            <Card className="p-4 gradient-card border-border/40">
              <div className="text-sm text-muted-foreground mb-1">Sharpe Ratio</div>
              <div className="text-2xl font-bold font-mono">{vault.sharpe.toFixed(2)}</div>
            </Card>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <Button size="lg" className="gap-2" onClick={() => setShowDeposit(true)}>
              <Wallet className="h-4 w-4" />
              Deposit
            </Button>
            <Button size="lg" variant="outline" className="gap-2 bg-transparent">
              Withdraw
            </Button>
            <Button size="lg" variant="ghost" className="gap-2">
              View on Explorer
              <ArrowUpRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <section className="py-12">
        <div className="container mx-auto px-4">
          <Tabs defaultValue="performance" className="w-full">
            <TabsList className="mb-8">
              <TabsTrigger value="performance">Performance</TabsTrigger>
              <TabsTrigger value="holdings">Holdings</TabsTrigger>
              <TabsTrigger value="transactions">Transactions</TabsTrigger>
              <TabsTrigger value="info">Info</TabsTrigger>
              {process.env.NEXT_PUBLIC_ENABLE_DEMO_TRADING === '1' && (
                <TabsTrigger value="exec">Exec</TabsTrigger>
              )}
            </TabsList>

            <TabsContent value="performance" className="space-y-6">
              <Card className="p-6 gradient-card border-border/40">
                <h3 className="text-lg font-semibold mb-6">NAV / PnL Curve</h3>
                <PerformanceChart data={chartPoints} />
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Card className="p-4 gradient-card border-border/40">
                  <div className="text-sm text-muted-foreground mb-2">Annual Volatility</div>
                  <div className="text-xl font-bold font-mono">{vault.volatility.toFixed(1)}%</div>
                </Card>
                <Card className="p-4 gradient-card border-border/40">
                  <div className="text-sm text-muted-foreground mb-2">Max Drawdown</div>
                  <div className="text-xl font-bold text-destructive flex items-center gap-2">
                    <TrendingDown className="h-4 w-4" />
                    {vault.maxDrawdown.toFixed(1)}%
                  </div>
                </Card>
                <Card className="p-4 gradient-card border-border/40">
                  <div className="text-sm text-muted-foreground mb-2">Recovery Period</div>
                  <div className="text-xl font-bold font-mono">{vault.recoveryDays} days</div>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="holdings">
                {vault.type === "public" ? (
                <Card className="p-6 gradient-card border-border/40">
                  <h3 className="text-lg font-semibold mb-4">Current Holdings</h3>
                  <p className="text-muted-foreground">Holdings data will be displayed here for public vaults.</p>
                </Card>
              ) : (
                <Card className="p-6 gradient-card border-border/40 text-center">
                  <Lock className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Private Vault</h3>
                  <p className="text-muted-foreground">
                    Holdings are not disclosed for private vaults. Only NAV and performance metrics are visible.
                  </p>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="transactions">
              <Card className="p-6 gradient-card border-border/40">
                <h3 className="text-lg font-semibold mb-4">Recent Events</h3>
                <EventsFeed vaultId={vaultId} />
              </Card>
            </TabsContent>

            <TabsContent value="info">
              <Card className="p-6 gradient-card border-border/40">
                <h3 className="text-lg font-semibold mb-6">Vault Information</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between py-3 border-b border-border/40">
                    <span className="text-muted-foreground">Performance Fee</span>
                    <span className="font-semibold">{vault.performanceFee}%</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border/40">
                    <span className="text-muted-foreground">Management Fee</span>
                    <span className="font-semibold">{vault.managementFee}%</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border/40">
                    <span className="text-muted-foreground">Minimum Lock Period</span>
                    <span className="font-semibold">{(chain.lockDays ?? vault.lockDays)} day(s)</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border/40">
                    <span className="text-muted-foreground">Manager Stake</span>
                    <span className="font-semibold">{vault.managerStake.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <span className="text-muted-foreground">Total Shares</span>
                    <span className="font-semibold font-mono">{(chain.totalSupply ?? vault.totalShares).toLocaleString()}</span>
                  </div>
                </div>
              </Card>
            </TabsContent>

            {process.env.NEXT_PUBLIC_ENABLE_DEMO_TRADING === '1' && (
              <TabsContent value="exec">
                <ExecPanel vaultId={vaultId} />
              </TabsContent>
            )}
          </Tabs>
        </div>
      </section>

      <DepositModal open={showDeposit} onOpenChange={setShowDeposit} vault={vault} />
    </>
  )
}
