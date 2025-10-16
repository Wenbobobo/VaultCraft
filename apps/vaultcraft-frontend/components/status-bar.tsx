"use client"

import { useEffect, useState } from "react"
import { BACKEND_URL } from "@/lib/config"

type Flags = {
  enable_sdk: boolean
  enable_live_exec: boolean
  enable_user_ws: boolean
  enable_snapshot_daemon: boolean
  address?: string | null
  allowed_symbols?: string
}

type Net = { rpc?: string | null; chainId?: number | null; block?: number | null }

export function StatusBar() {
  const [flags, setFlags] = useState<Flags | null>(null)
  const [net, setNet] = useState<Net | null>(null)

  useEffect(() => {
    let alive = true
    async function load() {
      try {
        const r = await fetch(`${BACKEND_URL}/api/v1/status`, { cache: "no-store" })
        if (!r.ok) return
        const b = await r.json()
        if (!alive) return
        setFlags(b.flags)
        setNet(b.network)
      } catch {}
    }
    load()
    const id = setInterval(load, 10000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  if (!flags) return null
  const mode = flags.enable_live_exec ? "Live" : "Dry-run"
  const modeColor = flags.enable_live_exec ? "text-green-400" : "text-yellow-400"
  return (
    <div className="text-xs text-muted-foreground flex items-center gap-4 px-4 py-2 border-b border-border/40">
      <div>Mode: <span className={`${modeColor} font-mono`}>{mode}</span></div>
      <div>SDK: <span className={flags.enable_sdk ? "text-green-400" : "text-yellow-400"}>{flags.enable_sdk ? "on" : "off"}</span></div>
      <div>Listener: <span className={flags.enable_user_ws ? "text-green-400" : "text-muted-foreground"}>{flags.enable_user_ws ? "on" : "off"}</span></div>
      {flags.allowed_symbols && (<div>Symbols: <span className="font-mono">{flags.allowed_symbols}</span></div>)}
      {net && (
        <div className="ml-auto">RPC: <span className="font-mono">{net.chainId ?? "?"}</span> · Block: <span className="font-mono">{net.block ?? "?"}</span></div>
      )}
    </div>
  )
}

