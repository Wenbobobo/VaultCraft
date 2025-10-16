"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown, Clock, ArrowUpRight } from "lucide-react"
import Link from "next/link"

// Mock portfolio data
const mockPositions = [
  {
    vaultId: "0x1234...5678",
    vaultName: "Alpha Momentum Strategy",
    shares: 1250.5,
    costBasis: 1.12,
    currentNav: 1.245,
    unlockDate: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000),
  },
  {
    vaultId: "0xabcd...efgh",
    vaultName: "DeFi Yield Optimizer",
    shares: 850.25,
    costBasis: 1.05,
    currentNav: 1.18,
    unlockDate: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
  },
]

export function PortfolioView() {
  const totalValue = mockPositions.reduce((sum, pos) => sum + pos.shares * pos.currentNav, 0)
  const totalCost = mockPositions.reduce((sum, pos) => sum + pos.shares * pos.costBasis, 0)
  const totalPnL = totalValue - totalCost
  const totalPnLPercent = (totalPnL / totalCost) * 100

  return (
    <section className="py-12">
      <div className="container mx-auto px-4">
        <div className="mb-10">
          <h1 className="text-3xl font-bold mb-3">My Portfolio</h1>
          <p className="text-muted-foreground">Track your vault positions and performance</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card className="p-6 gradient-card border-border/40">
            <div className="text-sm text-muted-foreground mb-2">Total Value</div>
            <div className="text-3xl font-bold font-mono">${totalValue.toFixed(2)}</div>
          </Card>
          <Card className="p-6 gradient-card border-border/40">
            <div className="text-sm text-muted-foreground mb-2">Total Cost</div>
            <div className="text-3xl font-bold font-mono">${totalCost.toFixed(2)}</div>
          </Card>
          <Card className="p-6 gradient-card border-border/40">
            <div className="text-sm text-muted-foreground mb-2">Total P&L</div>
            <div
              className={`text-3xl font-bold flex items-center gap-2 ${totalPnL >= 0 ? "text-success" : "text-destructive"}`}
            >
              {totalPnL >= 0 ? <TrendingUp className="h-6 w-6" /> : <TrendingDown className="h-6 w-6" />}$
              {Math.abs(totalPnL).toFixed(2)} ({totalPnLPercent >= 0 ? "+" : ""}
              {totalPnLPercent.toFixed(2)}%)
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          {mockPositions.map((position) => {
            const currentValue = position.shares * position.currentNav
            const cost = position.shares * position.costBasis
            const pnl = currentValue - cost
            const pnlPercent = (pnl / cost) * 100
            const isLocked = position.unlockDate > new Date()

            return (
              <Card key={position.vaultId} className="p-6 gradient-card border-border/40">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold mb-2">{position.vaultName}</h3>
                    <p className="text-sm text-muted-foreground font-mono">{position.vaultId}</p>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-8">
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Shares</div>
                      <div className="font-semibold font-mono">{position.shares.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Current Value</div>
                      <div className="font-semibold font-mono">${currentValue.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">P&L</div>
                      <div
                        className={`font-semibold flex items-center gap-1 ${pnl >= 0 ? "text-success" : "text-destructive"}`}
                      >
                        {pnl >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                        {pnlPercent >= 0 ? "+" : ""}
                        {pnlPercent.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Status</div>
                      {isLocked ? (
                        <Badge variant="secondary" className="gap-1">
                          <Clock className="h-3 w-3" />
                          Locked
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-success border-success/40">
                          Unlocked
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Link href={`/vault/${position.vaultId}`}>
                      <Button variant="outline" size="sm" className="gap-2 bg-transparent">
                        View
                        <ArrowUpRight className="h-3 w-3" />
                      </Button>
                    </Link>
                    <Button size="sm" disabled={isLocked}>
                      Withdraw
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      </div>
    </section>
  )
}
