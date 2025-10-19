"use client"

import { useEffect, useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { useWallet } from "@/hooks/use-wallet"
import { BACKEND_URL, DEFAULT_ASSET_ADDRESS } from "@/lib/config"
import { ethers } from "ethers"
import { ExecPanel } from "@/components/exec-panel"
import Link from "next/link"

const MGMT_ABI = [
  // writes
  "function setWhitelist(address u, bool allowed)",
  "function setLockMinDays(uint256 daysMin)",
  "function setPerformanceFee(uint256 pBps)",
  "function pause()",
  "function unpause()",
  // reads
  "function asset() view returns (address)",
  "function admin() view returns (address)",
  "function manager() view returns (address)",
  "function guardian() view returns (address)",
  "function performanceFeeP() view returns (uint256)",
  "function lockMinSeconds() view returns (uint256)",
  "function adapterAllowed(address) view returns (bool)",
]

export default function ManagerPage() {
  const { connect, isHyper, address, ensureHyperChain } = useWallet()
  const [asset, setAsset] = useState(DEFAULT_ASSET_ADDRESS)
  const [name, setName] = useState("VaultCraft")
  const [symbol, setSymbol] = useState("VSHARE")
  const [isPrivate, setIsPrivate] = useState(false)
  const [pBps, setPBps] = useState("1000")
  const [lockDays, setLockDays] = useState("1")
  const [deployMsg, setDeployMsg] = useState<string | null>(null)
  const [deployErr, setDeployErr] = useState<string | null>(null)
  const [vaultAddr, setVaultAddr] = useState("")
  const [mgmtMsg, setMgmtMsg] = useState<string | null>(null)
  const validVault = ethers.isAddress(vaultAddr)
  const [adapterAddr, setAdapterAddr] = useState("")
  const [newManager, setNewManager] = useState("")
  const [newGuardian, setNewGuardian] = useState("")
  const [readInfo, setReadInfo] = useState<any | null>(null)
  const [devMsg, setDevMsg] = useState<string | null>(null)
  const [assetInfo, setAssetInfo] = useState<{ symbol?: string; decimals?: number } | null>(null)
  const [assetBalance, setAssetBalance] = useState<string | null>(null)
  const [assetLoading, setAssetLoading] = useState(false)
  const [lastDeployed, setLastDeployed] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!ethers.isAddress(asset)) {
        setAssetInfo(null)
        setAssetBalance(null)
        return
      }
      try {
        setAssetLoading(true)
        const provider = new ethers.JsonRpcProvider(process.env.NEXT_PUBLIC_RPC_URL)
        const erc = new ethers.Contract(
          asset,
          [
            "function symbol() view returns (string)",
            "function decimals() view returns (uint8)",
            "function balanceOf(address) view returns (uint256)",
          ],
          provider
        )
        const [sym, decRaw] = await Promise.all([
          erc.symbol().catch(() => ""),
          erc.decimals().catch(() => 18),
        ])
        let bal: string | null = null
        const dec = Number(decRaw)
        if (address) {
          try {
            const raw = await erc.balanceOf(address)
            bal = ethers.formatUnits(raw, dec)
          } catch {}
        }
        if (!cancelled) {
          setAssetInfo({ symbol: sym || undefined, decimals: dec })
          setAssetBalance(bal)
        }
      } catch {
        if (!cancelled) {
          setAssetInfo(null)
          setAssetBalance(null)
        }
      } finally {
        if (!cancelled) setAssetLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [asset, address])

  useEffect(() => {
    if (DEFAULT_ASSET_ADDRESS || asset) return
    let cancelled = false
    fetch(`${BACKEND_URL}/api/v1/vaults`)
      .then((r) => r.json())
      .then((res) => {
        if (cancelled) return
        const vaults = Array.isArray(res?.vaults) ? res.vaults : []
        const withAsset = vaults.find((v: any) => v?.asset && typeof v.asset === "string")
        if (withAsset?.asset) {
          setAsset(withAsset.asset)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [asset])

  async function deploy() {
    setDeployErr(null); setDeployMsg(null)
    try {
      await connect()
      await ensureHyperChain?.()
      if (!isHyper) throw new Error("Please switch to Hyper Testnet (chain 998)")
      if (!ethers.isAddress(asset)) throw new Error("Please enter a valid asset ERC20 address (e.g. Hyper USDC)")
      // fetch artifact from backend
      const r = await fetch(`${BACKEND_URL}/api/v1/artifacts/vault`, { headers: { Accept: "application/json" } })
      let art: any = null
      try {
        art = await r.json()
      } catch {
        art = null
      }
      if (!r.ok) {
        const statusMsg = art?.error || `Artifact fetch failed (status ${r.status})`
        throw new Error(statusMsg)
      }
      if (!art?.bytecode || !art?.abi) {
        throw new Error(art?.error || "Artifact not available. Run `npx hardhat compile` then restart the backend.")
      }
      const eth = (window as any).ethereum
      const provider = new ethers.BrowserProvider(eth)
      const signer = await provider.getSigner()
      const admin = await signer.getAddress()
      const args = [asset, name, symbol, admin, admin, admin, isPrivate, BigInt(pBps), BigInt(lockDays)]
      const fac = new ethers.ContractFactory(art.abi, art.bytecode, signer)
      const tx = await fac.deploy(...args)
      setDeployMsg(`Deploying... ${tx.deploymentTransaction()?.hash}`)
      const deployed = await tx.waitForDeployment()
      const addr = await deployed.getAddress()
      setVaultAddr(addr)
      setDeployMsg(`Deployed: ${addr}`)
      setLastDeployed(addr)
      // optional: register for discovery
      try { await fetch(`${BACKEND_URL}/api/v1/register_deployment?vault=${addr}&asset=${asset}`, { method: 'POST' }) } catch {}
    } catch (e: any) {
      const raw = e?.shortMessage || e?.message || String(e)
      if (typeof raw === "string" && raw.includes("Failed to fetch")) {
        setDeployErr("无法访问后端 API。请确认 FastAPI 服务已运行，并在 .env 中设置 NEXT_PUBLIC_BACKEND_URL 指向后端主机（例如 http://localhost:8000）。")
      } else {
        setDeployErr(raw)
      }
    }
  }

  async function call(fn: string, ...params: any[]) {
    setMgmtMsg(null)
    try {
      await connect()
      const eth = (window as any).ethereum
      const provider = new ethers.BrowserProvider(eth)
      const signer = await provider.getSigner()
      const c = new ethers.Contract(vaultAddr, MGMT_ABI, signer)
      // @ts-ignore
      const tx = await c[fn](...params)
      setMgmtMsg(`${fn}... ${tx.hash}`)
      await tx.wait()
      setMgmtMsg(`${fn} confirmed: ${tx.hash}`)
    } catch (e: any) {
      setMgmtMsg(e?.shortMessage || e?.message || String(e))
    }
  }

  async function readBack() {
    setMgmtMsg(null)
    setReadInfo(null)
    try {
      const eth = (window as any).ethereum
      const provider = new ethers.BrowserProvider(eth)
      const c = new ethers.Contract(vaultAddr, MGMT_ABI, provider)
      const [assetAddr, admin, manager, guardian, perf, lock] = await Promise.all([
        c.asset(), c.admin(), c.manager(), c.guardian(), c.performanceFeeP(), c.lockMinSeconds()
      ])
      let adapterAllowed = false
      if (ethers.isAddress(adapterAddr)) {
        try { adapterAllowed = await c.adapterAllowed(adapterAddr) } catch {}
      }
      setReadInfo({ asset: assetAddr, admin, manager, guardian, performanceFeeP: Number(perf), lockDays: Math.floor(Number(lock)/86400), adapterAllowed })
    } catch (e: any) {
      setMgmtMsg(e?.shortMessage || e?.message || String(e))
    }
  }

  async function deployMockAsset() {
    setDevMsg(null)
    try {
      await connect()
      const artRes = await fetch(`${BACKEND_URL}/api/v1/artifacts/mockerc20`, { headers: { Accept: "application/json" } })
      let art: any = null
      try {
        art = await artRes.json()
      } catch {
        art = null
      }
      if (!artRes.ok) {
        throw new Error(art?.error || `MockERC20 artifact fetch failed (status ${artRes.status})`)
      }
      if (!art?.bytecode || !art?.abi) throw new Error(art?.error || "MockERC20 artifact not available. Run `npx hardhat compile` then restart backend.")
      const eth = (window as any).ethereum
      const provider = new ethers.BrowserProvider(eth)
      const signer = await provider.getSigner()
      const fac = new ethers.ContractFactory(art.abi, art.bytecode, signer)
      const tx = await fac.deploy("USD Stable", "USDS")
      setDevMsg(`Deploying MockERC20... ${tx.deploymentTransaction()?.hash}`)
      const deployed = await tx.waitForDeployment()
      const addr = await deployed.getAddress()
      // Mint demo balance to signer
      const erc = new ethers.Contract(addr, art.abi, signer)
      const amt = ethers.parseEther("1000000")
      const txm = await erc.mint(await signer.getAddress(), amt)
      setDevMsg(`Minting... ${txm.hash}`)
      await txm.wait()
      setAsset(addr)
      setDevMsg(`Mock asset deployed: ${addr} and minted 1,000,000 to you`)
    } catch (e: any) {
      const raw = e?.shortMessage || e?.message || String(e)
      if (typeof raw === "string" && raw.includes("Failed to fetch")) {
        setDevMsg("无法访问后端 API。请确认 FastAPI 服务运行中，或配置 NEXT_PUBLIC_BACKEND_URL 指向后端地址。")
      } else {
        setDevMsg(raw)
      }
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <section className="py-12">
          <div className="container mx-auto px-4 space-y-6">
            <Card className="p-6 gradient-card border-border/40">
              <h2 className="text-lg font-semibold mb-4">Launch Checklist</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1 text-sm">
                  <div className="text-muted-foreground">Asset Address</div>
                  <div className="font-mono text-xs break-all">{asset || "(enter ERC20 address)"}</div>
                  {assetLoading ? (
                    <div className="text-xs text-muted-foreground">Loading asset metadata…</div>
                  ) : assetInfo ? (
                    <div className="text-xs text-muted-foreground">{assetInfo.symbol ? `${assetInfo.symbol} · ` : ""}{assetInfo.decimals ?? "?"} decimals</div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      Unable to read token metadata. Set <code className="font-mono">NEXT_PUBLIC_DEFAULT_ASSET_ADDRESS</code> in <code>.env</code> (e.g. Hyper Testnet USDC) or use the dev helper below.
                    </div>
                  )}
                </div>
                <div className="space-y-1 text-sm">
                  <div className="text-muted-foreground">Manager Balance</div>
                  <div className="font-mono text-xs">{assetBalance ? `${Number(assetBalance).toFixed(4)} ${assetInfo?.symbol || "tokens"}` : "(connect wallet)"}</div>
                  <div className="text-xs text-muted-foreground">Ensure sufficient USDC for self-stake & investor testing.</div>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="text-muted-foreground">Network</div>
                  <div className="text-xs">{isHyper ? "Hyper Testnet (998)" : "Switch wallet to Hyper Testnet"}</div>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="text-muted-foreground">Last Deployed Vault</div>
                  {lastDeployed ? (
                    <div className="text-xs">
                      <Link href={`/vault/${lastDeployed}`} className="text-primary underline">{lastDeployed.slice(0, 10)}…</Link>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">Deploy to populate</div>
                  )}
                </div>
              </div>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="p-6 gradient-card border-border/40">
              <h2 className="text-lg font-semibold mb-4">Deploy New Vault</h2>
              <div className="space-y-3">
                <div>
                  <Label>Asset ERC20 Address</Label>
                  <Input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="0x..." />
                  {!DEFAULT_ASSET_ADDRESS && (
                    <div className="mt-2 flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={deployMockAsset}>Dev: Deploy MockERC20 + Mint</Button>
                      {devMsg && (<div className="text-xs text-muted-foreground break-all">{devMsg}</div>)}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Name</Label>
                    <Input value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div>
                    <Label>Symbol</Label>
                    <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label>Perf Fee (bps)</Label>
                    <Input value={pBps} onChange={(e) => setPBps(e.target.value)} />
                  </div>
                  <div>
                    <Label>Lock Days</Label>
                    <Input value={lockDays} onChange={(e) => setLockDays(e.target.value)} />
                  </div>
                  <div className="flex items-end gap-2">
                    <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} />
                    <Label>Private</Label>
                  </div>
                </div>
                <Button onClick={deploy}>Deploy</Button>
                {deployErr && (<div className="text-sm text-destructive">{deployErr}</div>)}
                {deployMsg && (<div className="text-xs text-muted-foreground break-all">{deployMsg}</div>)}
              </div>
              </Card>

              <Card className="p-6 gradient-card border-border/40">
                <h2 className="text-lg font-semibold mb-4">Manage Vault</h2>
                <div className="space-y-3">
                <div>
                  <Label>Vault Address</Label>
                  <Input value={vaultAddr} onChange={(e) => setVaultAddr(e.target.value)} placeholder="0x..." />
                  {validVault && (
                    <div className="mt-2 flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={readBack}>Read Current</Button>
                      {readInfo && (
                        <div className="text-xs text-muted-foreground">
                          <div>Asset {readInfo.asset}</div>
                          <div>Admin {readInfo.admin}</div>
                          <div>Manager {readInfo.manager}</div>
                          <div>Guardian {readInfo.guardian}</div>
                          <div>Perf Fee {readInfo.performanceFeeP} bps</div>
                          <div>Lock {readInfo.lockDays} day(s)</div>
                          {ethers.isAddress(adapterAddr) && <div>Adapter allowed: {String(readInfo.adapterAllowed)}</div>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Button onClick={() => call('pause')}>Pause</Button>
                  <Button variant="outline" onClick={() => call('unpause')}>Unpause</Button>
                </div>
                <div className="grid grid-cols-3 gap-3 items-end">
                  <div className="col-span-2">
                    <Label>Whitelist Address</Label>
                    <Input id="wl" placeholder="0x..." />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => {
                      const el = document.getElementById('wl') as HTMLInputElement
                      call('setWhitelist', el.value, true)
                    }}>Allow</Button>
                    <Button size="sm" variant="outline" onClick={() => {
                      const el = document.getElementById('wl') as HTMLInputElement
                      call('setWhitelist', el.value, false)
                    }}>Revoke</Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 items-end">
                  <div>
                    <Label>Perf Fee (bps)</Label>
                    <Input id="pf" placeholder="1000" />
                  </div>
                  <Button onClick={() => { const el = document.getElementById('pf') as HTMLInputElement; call('setPerformanceFee', BigInt(el.value||'0')) }}>Update</Button>
                </div>
                <div className="grid grid-cols-2 gap-3 items-end">
                  <div>
                    <Label>Lock Days</Label>
                    <Input id="ld" placeholder="1" />
                  </div>
                  <Button onClick={() => { const el = document.getElementById('ld') as HTMLInputElement; call('setLockMinDays', BigInt(el.value||'0')) }}>Update</Button>
                </div>
                <div className="grid grid-cols-3 gap-3 items-end">
                  <div className="col-span-2">
                    <Label>Adapter Address</Label>
                    <Input value={adapterAddr} onChange={(e)=>setAdapterAddr(e.target.value)} placeholder="0x..." />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => call('setAdapter', adapterAddr, true)}>Allow</Button>
                    <Button size="sm" variant="outline" onClick={() => call('setAdapter', adapterAddr, false)}>Revoke</Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 items-end">
                  <div>
                    <Label>New Manager</Label>
                    <Input value={newManager} onChange={(e)=>setNewManager(e.target.value)} placeholder="0x..." />
                  </div>
                  <Button onClick={()=> call('setManager', newManager)}>Update Manager</Button>
                </div>
                <div className="grid grid-cols-2 gap-3 items-end">
                  <div>
                    <Label>New Guardian</Label>
                    <Input value={newGuardian} onChange={(e)=>setNewGuardian(e.target.value)} placeholder="0x..." />
                  </div>
                  <Button onClick={()=> call('setGuardian', newGuardian)}>Update Guardian</Button>
                </div>
                  {mgmtMsg && (<div className="text-xs text-muted-foreground break-all">{mgmtMsg}</div>)}
                </div>
              </Card>

              <Card className="p-6 gradient-card border-border/40">
                <h2 className="text-lg font-semibold mb-4">Perps Execution (Manager)</h2>
                {!validVault ? (
                  <div className="text-sm text-muted-foreground">Enter a valid Vault address above to enable execution panel.</div>
                ) : (
                  <ExecPanel vaultId={vaultAddr} />
                )}
              </Card>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
