"use client"

import { useState, useEffect, useCallback } from "react"
import { BACKEND_URL } from "@/lib/config"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"

const VENUE_SYMBOLS: Record<string, string[]> = {
  hyper: ["ETH", "BTC"],
  mock_gold: ["XAU"],
}

type ExecPanelProps = {
  vaultId: string
  activeSymbol?: string
  activeVenue?: string
  onSymbolChange?: (symbol: string, venue: string) => void
}

export function ExecPanel({ vaultId, activeSymbol, activeVenue, onSymbolChange }: ExecPanelProps) {
  const initialVenue = activeVenue ?? "hyper"
  const initialSymbol = activeSymbol ?? (VENUE_SYMBOLS[initialVenue] ?? VENUE_SYMBOLS["hyper"])[0]
  const [venue, setVenue] = useState(initialVenue)
  const [symbol, setSymbol] = useState(initialSymbol)
  const [size, setSize] = useState("0.1")
  const [side, setSide] = useState<"buy" | "sell">("buy")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reduceOnly, setReduceOnly] = useState(false)
  const [leverage, setLeverage] = useState<string>("")
  const [orderType, setOrderType] = useState<"market" | "limit">("market")
  const [limitPrice, setLimitPrice] = useState<string>("")
  const [timeInForce, setTimeInForce] = useState<string>("Gtc")
  const [stopLoss, setStopLoss] = useState<string>("")
  const [takeProfit, setTakeProfit] = useState<string>("")
  const [minNotional, setMinNotional] = useState<number | null>(null)
  const [levRange, setLevRange] = useState<[number, number] | null>(null)
  const { toast } = useToast()

  // Load risk hints from backend status for UX prompts
  const loadRisk = useCallback(async () => {
    try {
      const qs = vaultId ? `?vault=${vaultId}` : ""
      const r = await fetch(`${BACKEND_URL}/api/v1/status${qs}`, { cache: "no-store" })
      if (!r.ok) return
      const b = await r.json()
      const mn = b?.flags?.exec_min_notional_usd
      if (typeof mn === 'number') setMinNotional(mn)
      const minL = b?.flags?.exec_min_leverage, maxL = b?.flags?.exec_max_leverage
      if (typeof minL === 'number' && typeof maxL === 'number') setLevRange([minL, maxL])
    } catch {}
  }, [vaultId])

  useEffect(() => {
    void loadRisk()
  }, [loadRisk])

  useEffect(() => {
    if (activeVenue && activeVenue !== venue) {
      setVenue(activeVenue)
      const allowed = VENUE_SYMBOLS[activeVenue] ?? VENUE_SYMBOLS["hyper"]
      if (!allowed.includes(symbol)) {
        setSymbol(allowed[0])
      }
    }
  }, [activeVenue, symbol, venue])

  useEffect(() => {
    if (activeSymbol && activeSymbol !== symbol) {
      setSymbol(activeSymbol)
    }
  }, [activeSymbol, symbol])

  function mapPretradeError(s: string | undefined): string {
    if (!s) return "Pretrade check failed"
    const t = s.toLowerCase()
    if (t.includes("venue")) return "Venue not allowed"
    if (t.includes("symbol") && t.includes("not allowed")) return "Symbol not in allowlist"
    if (t.includes("leverage")) return "Leverage out of bounds"
    if (t.includes("below minimum") || t.includes("minimum value")) return "Notional below minimum ($10)"
    if (t.includes("size") || t.includes("notional")) return "Size exceeds risk limit"
    if (t.includes("side")) return "Invalid side"
    return s
  }

  function extractAckError(body: any): string | null {
    try {
      const ack = body?.payload?.ack ?? body?.ack ?? body
      const js = typeof ack === 'string' ? ack : JSON.stringify(ack)
      const s = js.toLowerCase()
      if (s.includes('order must have minimum value')) return 'Notional below minimum ($10)'
      if (s.includes('too far from oracle')) return 'Close rejected by price band. Try again shortly.'
      if (s.includes('no position')) return 'No position to close'
      if (s.includes('error')) return 'Exchange rejected the order'
      return null
    } catch { return null }
  }

  async function send(path: string) {
    setBusy(true)
    setMsg(null)
    setError(null)
    try {
      if (orderType === "limit") {
        const px = parseFloat(limitPrice)
        if (!limitPrice || Number.isNaN(px) || px <= 0) {
          setError("Limit price required for limit orders")
          return
        }
      }
      // pretrade check
      const pre = new URLSearchParams()
      pre.set("symbol", symbol)
      pre.set("venue", venue)
      pre.set("size", size)
      pre.set("side", path.includes("open") ? side : "close")
      if (reduceOnly) pre.set("reduce_only", "true")
      if (leverage) pre.set("leverage", leverage)
      if (orderType) pre.set("order_type", orderType)
      const preUrl = `${BACKEND_URL}/api/v1/pretrade?${pre.toString()}`
      const pr = await fetch(preUrl)
      const pj = await pr.json()
      if (!pj.ok) {
        setError(mapPretradeError(pj.error))
        return
      }
      const params = new URLSearchParams()
      params.set("vault", vaultId)
      params.set("symbol", symbol)
      params.set("venue", venue)
      if (path.includes("open")) {
        params.set("size", size)
        params.set("side", side)
        if (reduceOnly) params.set("reduce_only", "true")
        if (leverage) params.set("leverage", leverage)
        params.set("order_type", orderType)
        if (orderType === "limit" && limitPrice) params.set("limit_price", limitPrice)
        if (orderType === "limit" && timeInForce) params.set("time_in_force", timeInForce)
        if (takeProfit) params.set("take_profit", takeProfit)
        if (stopLoss) params.set("stop_loss", stopLoss)
      } else {
        params.set("size", size)
      }
      const url = `${BACKEND_URL}${path}?${params.toString()}`
      const r = await fetch(url, { method: "POST" })
      const body = await r.json()
      const ackErr = extractAckError(body)
      if (ackErr) {
        setError(ackErr)
        toast({ title: "Execution warning", description: ackErr, variant: "destructive" })
      }
      const attempts = typeof body?.attempts === "number" ? body.attempts : 1
      if (!ackErr && attempts > 1) {
        toast({ title: "Retried", description: `Exchange accepted on attempt ${attempts}.`, variant: "default" })
      }
      setMsg(JSON.stringify(body, null, 2))
      if (body?.ok && !ackErr) {
        toast({ title: path.includes("open") ? "Order sent" : "Close sent", description: body.dry_run ? "Dry-run payload generated" : "Check events feed for fills." })
      } else if (body?.error) {
        toast({ title: "Execution failed", description: body.error, variant: "destructive" })
      }
    } catch (e: any) {
      setError(e?.message || String(e))
      toast({ title: "Execution error", description: e?.message || String(e), variant: "destructive" })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4 rounded-md border border-border/40">
      <div className="text-sm text-muted-foreground mb-2">Demo Exec (dry-run unless enabled)</div>
      <div className="flex flex-wrap gap-2 items-center mb-2">
        <select
          aria-label="Venue"
          value={venue}
          onChange={(e) => {
            const nextVenue = e.target.value
            setVenue(nextVenue)
            const allowed = VENUE_SYMBOLS[nextVenue] ?? VENUE_SYMBOLS["hyper"]
            if (!allowed.includes(symbol)) {
              const nextSymbol = allowed[0]
              setSymbol(nextSymbol)
              onSymbolChange?.(nextSymbol, nextVenue)
            }
          }}
          className="bg-transparent border rounded px-2 py-1"
        >
          <option value="hyper">Hyper Perps</option>
          <option value="mock_gold">Mock Gold (XAU)</option>
        </select>
        <select
          value={symbol}
          onChange={(e) => {
            const next = e.target.value
            setSymbol(next)
            onSymbolChange?.(next, venue)
          }}
          className="bg-transparent border rounded px-2 py-1"
        >
          {(VENUE_SYMBOLS[venue] ?? VENUE_SYMBOLS["hyper"]).map((opt) => (
            <option key={opt}>{opt}</option>
          ))}
        </select>
        <input value={size} onChange={(e) => setSize(e.target.value)} className="bg-transparent border rounded px-2 py-1 w-24" />
        <select value={side} onChange={(e) => setSide(e.target.value as any)} className="bg-transparent border rounded px-2 py-1">
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select aria-label="Order Type" value={orderType} onChange={(e)=>setOrderType(e.target.value as "market"|"limit")} className="bg-transparent border rounded px-2 py-1">
          <option value="market">Market</option>
          <option value="limit">Limit</option>
        </select>
        <input placeholder="Leverage" value={leverage} onChange={(e)=>setLeverage(e.target.value)} className="bg-transparent border rounded px-2 py-1 w-24" />
        <label className="text-xs flex items-center gap-1">
          <input type="checkbox" checked={reduceOnly} onChange={(e)=>setReduceOnly(e.target.checked)} /> reduce-only
        </label>
        <Button size="sm" disabled={busy} onClick={() => send("/api/v1/exec/open")}>{busy ? "Sending..." : "Open"}</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => send("/api/v1/exec/close")}>{busy ? "Sending..." : "Close"}</Button>
      </div>
      {orderType === "limit" && (
        <div className="flex flex-wrap gap-2 mb-2 text-xs">
          <input
            placeholder="Limit price"
            value={limitPrice}
            onChange={(e) => setLimitPrice(e.target.value)}
            className="bg-transparent border rounded px-2 py-1 w-28"
          />
          <select
            aria-label="Time in force"
            value={timeInForce}
            onChange={(e) => setTimeInForce(e.target.value)}
            className="bg-transparent border rounded px-2 py-1"
          >
            <option value="Gtc">GTC</option>
            <option value="Ioc">IOC</option>
            <option value="Fok">FOK</option>
          </select>
        </div>
      )}
      <div className="flex flex-wrap gap-2 mb-2 text-xs">
        <input
          placeholder="Take profit"
          value={takeProfit}
          onChange={(e) => setTakeProfit(e.target.value)}
          className="bg-transparent border rounded px-2 py-1 w-28"
        />
        <input
          placeholder="Stop loss"
          value={stopLoss}
          onChange={(e) => setStopLoss(e.target.value)}
          className="bg-transparent border rounded px-2 py-1 w-28"
        />
      </div>
      {(minNotional != null || levRange) && (
        <div className="text-xs text-muted-foreground mb-2">
          Venue: {venue === "hyper" ? "Hyper Perps" : "Mock Gold"} {minNotional != null ? ` · Min notional $${minNotional}` : ""}
          {levRange ? ` · Lev ${levRange[0]}–${levRange[1]}x` : ""}
        </div>
      )}
      {error && (
        <div data-testid="exec-error" className="text-xs text-destructive mb-2">{error}</div>
      )}
      {msg && (
        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all">{msg}</pre>
      )}
    </div>
  )
}
