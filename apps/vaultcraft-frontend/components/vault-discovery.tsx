"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ArrowUpRight, Lock, Eye, TrendingUp, TrendingDown } from "lucide-react"
import Link from "next/link"

import { useEffect } from "react";
import { getVaults } from "@/lib/api";

// Mock data (fallback)
const fallbackVaults = [
  {
    id: "0x1234...5678",
    name: "Alpha Momentum Strategy",
    type: "public",
    aum: 4250000,
    sharpe: 2.34,
    annualReturn: 24.5,
    volatility: 12.3,
    maxDrawdown: -8.2,
    performanceFee: 10,
    managerStake: 8.5,
    isNew: false,
  },
  {
    id: "0x8765...4321",
    name: "Quant Arbitrage Fund",
    type: "private",
    aum: 8900000,
    sharpe: 3.12,
    annualReturn: 31.2,
    volatility: 9.8,
    maxDrawdown: -5.4,
    performanceFee: 15,
    managerStake: 12.0,
    isNew: false,
  },
  {
    id: "0xabcd...efgh",
    name: "DeFi Yield Optimizer",
    type: "public",
    aum: 2100000,
    sharpe: 1.89,
    annualReturn: 18.7,
    volatility: 14.2,
    maxDrawdown: -11.5,
    performanceFee: 10,
    managerStake: 6.2,
    isNew: true,
  },
  {
    id: "0xijkl...mnop",
    name: "Macro Trend Follower",
    type: "private",
    aum: 15600000,
    sharpe: 2.67,
    annualReturn: 28.3,
    volatility: 10.6,
    maxDrawdown: -7.8,
    performanceFee: 12,
    managerStake: 15.3,
    isNew: false,
  },
  {
    id: "0xqrst...uvwx",
    name: "Volatility Harvester",
    type: "public",
    aum: 3400000,
    sharpe: 2.01,
    annualReturn: 21.4,
    volatility: 13.1,
    maxDrawdown: -9.7,
    performanceFee: 10,
    managerStake: 7.8,
    isNew: false,
  },
  {
    id: "0xyzab...cdef",
    name: "Statistical Arbitrage",
    type: "private",
    aum: 6700000,
    sharpe: 2.89,
    annualReturn: 26.8,
    volatility: 9.2,
    maxDrawdown: -6.1,
    performanceFee: 15,
    managerStake: 10.5,
    isNew: true,
  },
]

export function VaultDiscovery() {
  const [filter, setFilter] = useState<"all" | "public" | "private">("all")
  const [sortBy, setSortBy] = useState<"sharpe" | "aum" | "return">("sharpe")
  const [q, setQ] = useState("")

  const [vaults, setVaults] = useState(fallbackVaults)

  useEffect(() => {
    let alive = true
    getVaults()
      .then((v) => {
        if (!alive) return
        // merge minimal API data into display-friendly mock-like shape with defaults
        const enriched = v.map((x) => ({
          id: x.id,
          name: x.name,
          type: x.type,
          aum: x.aum ?? 1_000_000,
          sharpe: 1.8,
          annualReturn: 20.0,
          volatility: 12.0,
          maxDrawdown: -8.0,
          performanceFee: 10,
          managerStake: 10.0,
          isNew: false,
        }))
        setVaults(enriched)
      })
      .catch(() => {
        // ignore; keep fallback
      })
    return () => {
      alive = false
    }
  }, [])

  const filteredVaults = vaults
    .filter((vault) => filter === "all" || vault.type === filter)
    .filter((v) => {
      if (!q) return true
      const s = q.toLowerCase()
      return v.name.toLowerCase().includes(s) || v.id.toLowerCase().includes(s)
    })
    .sort((a, b) => {
      if (sortBy === "sharpe") return b.sharpe - a.sharpe
      if (sortBy === "aum") return b.aum - a.aum
      return b.annualReturn - a.annualReturn
    })

  return (
    <section className="py-20">
      <div className="container mx-auto px-4">
        <div className="mb-10">
          <h2 className="text-3xl font-bold mb-2">Discover Vaults</h2>
          <p className="text-muted-foreground">Verified trader vaults with transparent performance metrics</p>
        </div>

        <div className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <Tabs value={filter} onValueChange={(v) => setFilter(v as any)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="public">Public</TabsTrigger>
              <TabsTrigger value="private">Private</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2">
            <input value={q} onChange={(e)=>setQ(e.target.value)} placeholder="Search by name or address" className="bg-transparent border rounded px-2 py-1 w-64" />
            <Button variant={sortBy === "sharpe" ? "secondary" : "ghost"} size="sm" onClick={() => setSortBy("sharpe")}>
              Sharpe
            </Button>
            <Button variant={sortBy === "aum" ? "secondary" : "ghost"} size="sm" onClick={() => setSortBy("aum")}>
              AUM
            </Button>
            <Button variant={sortBy === "return" ? "secondary" : "ghost"} size="sm" onClick={() => setSortBy("return")}>
              Return
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredVaults.map((vault) => (
            <Card key={vault.id} className="p-5 gradient-card hover:border-primary/30 transition-smooth group">
              <div className="mb-4 flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{vault.name}</h3>
                    {vault.isNew && (
                      <Badge variant="secondary" className="text-xs">
                        New
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    {vault.type === "public" ? <Eye className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                    <span className="capitalize">{vault.type}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2.5 mb-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">AUM</span>
                  <span className="font-semibold font-mono text-sm">${(vault.aum / 1000000).toFixed(1)}M</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Return</span>
                  <span className="font-semibold text-success flex items-center gap-1 text-sm">
                    <TrendingUp className="h-3.5 w-3.5" />
                    {vault.annualReturn.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Sharpe</span>
                  <span className="font-semibold font-mono text-sm">{vault.sharpe.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Drawdown</span>
                  <span className="font-semibold text-destructive flex items-center gap-1 text-sm">
                    <TrendingDown className="h-3.5 w-3.5" />
                    {vault.maxDrawdown.toFixed(1)}%
                  </span>
                </div>
              </div>

              <Link href={`/vault/${vault.id}`}>
                <Button className="w-full gap-2 group-hover:bg-primary/90 transition-smooth" size="sm">
                  View Details
                  <ArrowUpRight className="h-4 w-4" />
                </Button>
              </Link>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
