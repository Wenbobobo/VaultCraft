"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

export function ExecPanel({ vaultId }: { vaultId: string }) {
  const [symbol, setSymbol] = useState("ETH")
  const [size, setSize] = useState("0.1")
  const [side, setSide] = useState<"buy" | "sell">("buy")
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function send(path: string) {
    setBusy(true)
    setMsg(null)
    try {
      const params = new URLSearchParams()
      params.set("vault", vaultId)
      params.set("symbol", symbol)
      if (path.includes("open")) {
        params.set("size", size)
        params.set("side", side)
      } else {
        params.set("size", size)
      }
      const url = `${process.env.NEXT_PUBLIC_BACKEND_URL}${path}?${params.toString()}`
      const r = await fetch(url, { method: "POST" })
      const body = await r.json()
      setMsg(JSON.stringify(body))
    } catch (e: any) {
      setMsg(e?.message || String(e))
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
        <Button size="sm" disabled={busy} onClick={() => send("/api/v1/exec/open")}>Open</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => send("/api/v1/exec/close")}>Close</Button>
      </div>
      {msg && (
        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all">{msg}</pre>
      )}
    </div>
  )
}

