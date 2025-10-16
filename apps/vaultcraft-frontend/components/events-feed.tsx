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
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full ${e.type?.startsWith('exec') ? 'bg-blue-500/10 text-blue-300' : e.type === 'fill' ? 'bg-green-500/10 text-green-300' : 'bg-zinc-500/10 text-zinc-300'}`}>{e.type}</span>
                {e.status && (
                  <span className={`px-2 py-0.5 rounded-full ${e.status === 'ack' ? 'bg-green-500/10 text-green-300' : e.status === 'dry_run' ? 'bg-yellow-500/10 text-yellow-300' : e.status === 'rejected' ? 'bg-red-500/10 text-red-300' : 'bg-zinc-500/10 text-zinc-300'}`}>{e.status}</span>
                )}
              </div>
              {e.symbol && (
                <div className="text-muted-foreground mt-1">{e.symbol} {e.side} {e.size ?? ""}</div>
              )}
              {e.error && (
                <div className="text-destructive mt-1">{e.error}</div>
              )}
            </div>
            <div className="text-muted-foreground">{e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : ""}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
