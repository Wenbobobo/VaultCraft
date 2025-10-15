'use client'

import { useEffect, useMemo, useState } from 'react'
import { ethers } from 'ethers'

const VAULT_ABI = [
  'function ps() view returns (uint256)',
  'function totalAssets() view returns (uint256)',
  'function totalSupply() view returns (uint256)',
  'function performanceFeeP() view returns (uint256)',
  'function lockMinSeconds() view returns (uint256)',
  'function isPrivate() view returns (bool)'
]

export default function VaultClient({ address }: { address: string }) {
  const [unitNav, setUnitNav] = useState<string>('—')
  const [aum, setAum] = useState<string>('—')
  const [lockDays, setLockDays] = useState<string>('—')
  const [perfFee, setPerfFee] = useState<string>('—')
  const [supply, setSupply] = useState<string>('—')
  const [mode, setMode] = useState<'public'|'private'|'—'>('—')

  const provider = useMemo(() => {
    const url = process.env.NEXT_PUBLIC_RPC_URL
    return url ? new ethers.JsonRpcProvider(url) : null
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!provider) return
      try {
        const vault = new ethers.Contract(address, VAULT_ABI, provider)
        const [ps, assets, supply, fee, lock, priv] = await Promise.all([
          vault.ps(),
          vault.totalAssets(),
          vault.totalSupply(),
          vault.performanceFeeP(),
          vault.lockMinSeconds(),
          vault.isPrivate(),
        ])
        if (cancelled) return
        const nav = Number(ps) / 1e18
        setUnitNav(nav.toFixed(6))
        // assume stablecoin 1:1 for demo
        setAum(`$${Math.round(Number(assets) / 1e18).toLocaleString()}`)
        setLockDays(`${Math.floor(Number(lock) / 86400)} day`)
        setPerfFee(`${Number(fee) / 100}%`)
        setSupply((Number(supply) / 1e18).toLocaleString())
        setMode(priv ? 'private' : 'public')
      } catch (e) {
        console.error(e)
      }
    }
    load()
    return () => { cancelled = true }
  }, [address, provider])

  return (
    <>
      <section className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xl font-semibold">Vault {address}</div>
            <div className="text-xs text-slate-400 uppercase">{mode}</div>
          </div>
          <div className="kpi">
            <div className="label">AUM</div>
            <div className="value">{aum}</div>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-6">
          <div className="kpi"><div className="label">Unit NAV</div><div className="value">{unitNav}</div></div>
          <div className="kpi"><div className="label">Perf Fee</div><div className="value">{perfFee}</div></div>
          <div className="kpi"><div className="label">Lock</div><div className="value">{lockDays}</div></div>
          <div className="kpi"><div className="label">Supply</div><div className="value">{supply}</div></div>
        </div>
      </section>

      {mode === 'public' && (
        <section className="card">
          <div className="mb-2 text-slate-300">持仓（公募可见）</div>
          <div className="h-28 rounded bg-slate-800/60 grid place-items-center text-slate-400">待接入 Adapter / Router</div>
        </section>
      )}

      <section className="card">
        <div className="mb-2 text-slate-300">{mode === 'private' ? 'NAV/PnL（私募：不展示持仓）' : 'NAV/PnL'}</div>
        <div className="h-40 rounded bg-slate-800/60 grid place-items-center text-slate-400">图表占位（接入后端指标）</div>
      </section>
    </>
  )
}
