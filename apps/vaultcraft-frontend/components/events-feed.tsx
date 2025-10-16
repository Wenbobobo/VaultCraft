"use client"

import { useEffect, useState } from "react"
import { getEvents, type EventItem } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function EventsFeed({ vaultId }: { vaultId: string }) {
  const [items, setItems] = useState<EventItem[]>([])
  const [busy, setBusy] = useState(false)

  async function load() {
    setBusy(true)
    try {
      const ev = await getEvents(vaultId, 100)
      setItems(ev)
    } catch (e) {
      // ignore
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    let alive = true
    ;(async () => {
      setBusy(true)
      try {
        const ev = await getEvents(vaultId, 50)
        if (alive) setItems(ev)
      } finally {
        setBusy(false)
      }
    })()
    const id = setInterval(() => {
      getEvents(vaultId, 50).then((ev) => setItems(ev)).catch(() => {})
    }, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [vaultId])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Recent Events</div>
        <Button size="sm" variant="outline" disabled={busy} onClick={load}>Refresh</Button>
      </div>
      <div className="space-y-2">
        {items.length === 0 && (
          <div className="text-sm text-muted-foreground">No events yet.</div>
        )}
        {items.map((e, i) => (
          <div key={i} className="text-xs border border-border/40 rounded p-2 flex items-start justify-between">
            <div>
              <div className="font-mono">{e.type}{e.status ? ` • ${e.status}` : ""}</div>
              {e.symbol && (
                <div className="text-muted-foreground">{e.symbol} {e.side} {e.size ?? ""}</div>
              )}
              {e.error && (
                <div className="text-destructive">{e.error}</div>
              )}
            </div>
            <div className="text-muted-foreground">{e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : ""}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

