"use client"

import { useEffect, useMemo, useState } from "react"
import { ethers } from "ethers"

const VAULT_ABI = [
  "function ps() view returns (uint256)",
  "function totalAssets() view returns (uint256)",
  "function totalSupply() view returns (uint256)",
  "function performanceFeeP() view returns (uint256)",
  "function lockMinSeconds() view returns (uint256)",
  "function isPrivate() view returns (bool)",
]

export type OnchainVault = {
  unitNav?: number
  aum?: number
  lockDays?: number
  perfFeeP?: number
  totalSupply?: number
  isPrivate?: boolean
}

export function useOnchainVault(address: string) {
  const [data, setData] = useState<OnchainVault>({})
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
        setData({
          unitNav: nav,
          aum: Number(assets) / 1e18,
          lockDays: Math.floor(Number(lock) / 86400),
          perfFeeP: Number(fee),
          totalSupply: Number(supply) / 1e18,
          isPrivate: Boolean(priv),
        })
      } catch (e) {
        // silent fail; UI can rely on backend
        console.error(e)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [address, provider])

  return data
}

