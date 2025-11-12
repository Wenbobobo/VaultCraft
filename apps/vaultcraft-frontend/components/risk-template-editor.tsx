"use client"

import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"

type RiskTemplate = {
  allowedSymbols?: string
  minLeverage?: number
  maxLeverage?: number
  minNotionalUsd?: number
  maxNotionalUsd?: number
}

type RiskForm = {
  allowedSymbols: string
  minLeverage: string
  maxLeverage: string
  minNotionalUsd: string
  maxNotionalUsd: string
}

const emptyForm: RiskForm = {
  allowedSymbols: "",
  minLeverage: "",
  maxLeverage: "",
  minNotionalUsd: "",
  maxNotionalUsd: "",
}

function describeTemplate(tpl?: RiskTemplate | null): string {
  if (!tpl) return "—"
  const symbols = tpl.allowedSymbols || "ALL"
  const lev =
    tpl.minLeverage != null && tpl.maxLeverage != null
      ? `${tpl.minLeverage}–${tpl.maxLeverage}x`
      : tpl.minLeverage != null || tpl.maxLeverage != null
        ? `${tpl.minLeverage ?? ""}${tpl.maxLeverage ? `→${tpl.maxLeverage}` : ""}x`
        : "—"
  const notionals =
    tpl.minNotionalUsd != null || tpl.maxNotionalUsd != null
      ? `$${tpl.minNotionalUsd ?? 0}${tpl.maxNotionalUsd ? ` ~ $${tpl.maxNotionalUsd}` : "+"}`
      : "—"
  return `${symbols} · ${lev} · ${notionals}`
}

async function fetchJson(url: string, init?: RequestInit) {
  const resp = await fetch(url, init)
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(text || resp.statusText)
  }
  return resp.json()
}

export function RiskTemplateEditor({
  vaultId,
  backendUrl,
}: {
  vaultId?: string
  backendUrl: string
}) {
  const [form, setForm] = useState<RiskForm>(emptyForm)
  const [base, setBase] = useState<RiskTemplate | null>(null)
  const [effective, setEffective] = useState<RiskTemplate | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const disabled = !vaultId

  const loadRisk = useCallback(async () => {
    if (!vaultId) {
      setForm(emptyForm)
      setBase(null)
      setEffective(null)
      return
    }
    try {
      setLoading(true)
      setError(null)
      const data = await fetchJson(`${backendUrl}/api/v1/vaults/${vaultId}/risk`)
      setBase(data.base ?? null)
      setEffective(data.effective ?? null)
      const override: RiskTemplate | undefined = data.override
      if (override && Object.keys(override).length > 0) {
        setForm({
          allowedSymbols: override.allowedSymbols ?? "",
          minLeverage: override.minLeverage != null ? String(override.minLeverage) : "",
          maxLeverage: override.maxLeverage != null ? String(override.maxLeverage) : "",
          minNotionalUsd: override.minNotionalUsd != null ? String(override.minNotionalUsd) : "",
          maxNotionalUsd: override.maxNotionalUsd != null ? String(override.maxNotionalUsd) : "",
        })
      } else {
        setForm(emptyForm)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [backendUrl, vaultId])

  useEffect(() => {
    loadRisk()
  }, [loadRisk])

  const handleChange = (field: keyof RiskForm) => (event: ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const buildPayload = (): Record<string, string | number> => {
    const payload: Record<string, string | number> = {}
    if (form.allowedSymbols.trim()) {
      payload.allowedSymbols = form.allowedSymbols
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)
        .join(",")
    }
    const numericFields: Array<keyof RiskForm> = ["minLeverage", "maxLeverage", "minNotionalUsd", "maxNotionalUsd"]
    numericFields.forEach((field) => {
      const value = form[field]
      if (value.trim()) {
        const parsed = Number(value)
        if (!Number.isNaN(parsed)) {
          payload[field as string] = parsed
        }
      }
    })
    return payload
  }

  const save = async (clear = false) => {
    if (!vaultId) return
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const payload = clear ? {} : buildPayload()
      const data = await fetchJson(`${backendUrl}/api/v1/vaults/${vaultId}/risk`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      setBase(data.base ?? null)
      setEffective(data.effective ?? null)
      const override: RiskTemplate | undefined = data.override
      if (override && Object.keys(override).length > 0) {
        setForm({
          allowedSymbols: override.allowedSymbols ?? "",
          minLeverage: override.minLeverage != null ? String(override.minLeverage) : "",
          maxLeverage: override.maxLeverage != null ? String(override.maxLeverage) : "",
          minNotionalUsd: override.minNotionalUsd != null ? String(override.minNotionalUsd) : "",
          maxNotionalUsd: override.maxNotionalUsd != null ? String(override.maxNotionalUsd) : "",
        })
      } else {
        setForm(emptyForm)
      }
      setMessage(clear ? "已恢复平台默认风控" : "风险模板已保存")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const baseLabel = useMemo(() => describeTemplate(base), [base])
  const effectiveLabel = useMemo(() => describeTemplate(effective), [effective])

  return (
    <div className="rounded border border-border/40 bg-muted/20 p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Risk Template Override</h3>
          <p className="text-xs text-muted-foreground">
            针对单个 Vault 覆盖 Exec Service 风控参数（允许的标的、杠杆区间、名义金额限制）。留空则继承平台默认。
          </p>
        </div>
        {(loading || saving) && <span className="text-xs text-muted-foreground">{loading ? "加载中..." : "保存中..."}</span>}
      </div>
      {disabled ? (
        <div className="text-xs text-muted-foreground">请选择有效的 Vault 地址以编辑风险模板。</div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="risk-symbols">允许标的（逗号分隔）</Label>
              <Input
                id="risk-symbols"
                placeholder="BTC,ETH"
                value={form.allowedSymbols}
                onChange={handleChange("allowedSymbols")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="risk-minNotional">最小名义金额（USD）</Label>
              <Input
                id="risk-minNotional"
                placeholder="10"
                value={form.minNotionalUsd}
                onChange={handleChange("minNotionalUsd")}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="risk-minLev">最小杠杆</Label>
              <Input id="risk-minLev" placeholder="1" value={form.minLeverage} onChange={handleChange("minLeverage")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="risk-maxLev">最大杠杆</Label>
              <Input id="risk-maxLev" placeholder="5" value={form.maxLeverage} onChange={handleChange("maxLeverage")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="risk-maxNotional">最大名义金额（USD）</Label>
              <Input
                id="risk-maxNotional"
                placeholder="100000"
                value={form.maxNotionalUsd}
                onChange={handleChange("maxNotionalUsd")}
              />
            </div>
          </div>
          <Separator />
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <div>Base: {baseLabel}</div>
            <div>Effective: {effectiveLabel}</div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button size="sm" disabled={saving || loading} onClick={() => save(false)}>
              保存风险模板
            </Button>
            <Button size="sm" variant="outline" disabled={saving || loading} onClick={() => save(true)}>
              恢复平台默认
            </Button>
            <Button size="sm" variant="ghost" disabled={loading} onClick={loadRisk}>
              重新读取
            </Button>
          </div>
          {message && <div className="text-xs text-green-500">{message}</div>}
          {error && <div className="text-xs text-destructive">{error}</div>}
        </>
      )}
    </div>
  )
}
