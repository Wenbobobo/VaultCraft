"use client"

import { useState } from "react"
import { BACKEND_URL } from "@/lib/config"
import { Button } from "@/components/ui/button"

export function ExecPanel({ vaultId }: { vaultId: string }) {
  const [symbol, setSymbol] = useState("ETH")
  const [size, setSize] = useState("0.1")
  const [side, setSide] = useState<"buy" | "sell">("buy")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reduceOnly, setReduceOnly] = useState(false)
  const [leverage, setLeverage] = useState<string>("")

  function mapPretradeError(s: string | undefined): string {
    if (!s) return "Pretrade check failed"
    const t = s.toLowerCase()
    if (t.includes("symbol") && t.includes("not allowed")) return "Symbol not in allowlist"
    if (t.includes("leverage")) return "Leverage out of bounds"
    if (t.includes("below minimum")) return "Notional below minimum ($10)"
    if (t.includes("size") || t.includes("notional")) return "Size exceeds risk limit"
    if (t.includes("side")) return "Invalid side"
    return s
  }

  async function send(path: string) {
    setBusy(true)
    setMsg(null)
    setError(null)
    try {
      // pretrade check
      const pre = new URLSearchParams()
      pre.set("symbol", symbol)
      pre.set("size", size)
      pre.set("side", path.includes("open") ? side : "close")
      if (reduceOnly) pre.set("reduce_only", "true")
      if (leverage) pre.set("leverage", leverage)
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
      if (path.includes("open")) {
        params.set("size", size)
        params.set("side", side)
        if (reduceOnly) params.set("reduce_only", "true")
        if (leverage) params.set("leverage", leverage)
      } else {
        params.set("size", size)
      }
      const url = `${BACKEND_URL}${path}?${params.toString()}`
      const r = await fetch(url, { method: "POST" })
      const body = await r.json()
      setMsg(JSON.stringify(body, null, 2))
    } catch (e: any) {
      setError(e?.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4 rounded-md border border-border/40">
      <div className="text-sm text-muted-foreground mb-2">Demo Exec (dry-run unless enabled)</div>
      <div className="flex gap-2 items-center mb-2">
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="bg-transparent border rounded px-2 py-1">
          <option>ETH</option>
          <option>BTC</option>
        </select>
        <input value={size} onChange={(e) => setSize(e.target.value)} className="bg-transparent border rounded px-2 py-1 w-24" />
        <select value={side} onChange={(e) => setSide(e.target.value as any)} className="bg-transparent border rounded px-2 py-1">
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <input placeholder="Leverage" value={leverage} onChange={(e)=>setLeverage(e.target.value)} className="bg-transparent border rounded px-2 py-1 w-24" />
        <label className="text-xs flex items-center gap-1">
          <input type="checkbox" checked={reduceOnly} onChange={(e)=>setReduceOnly(e.target.checked)} /> reduce-only
        </label>
        <Button size="sm" disabled={busy} onClick={() => send("/api/v1/exec/open")}>{busy ? "Sending..." : "Open"}</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => send("/api/v1/exec/close")}>{busy ? "Sending..." : "Close"}</Button>
      </div>
      {error && (
        <div className="text-xs text-destructive mb-2">{error}</div>
      )}
      {msg && (
        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all">{msg}</pre>
      )}
    </div>
  )
}
