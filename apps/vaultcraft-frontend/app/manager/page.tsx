"use client"

import { useEffect, useMemo, useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { useWallet } from "@/hooks/use-wallet"
import { BACKEND_URL } from "@/lib/config"
import { ethers } from "ethers"
import { ExecPanel } from "@/components/exec-panel"

const MGMT_ABI = [
  "function setWhitelist(address u, bool allowed)",
  "function setLockMinDays(uint256 daysMin)",
  "function setPerformanceFee(uint256 pBps)",
  "function pause()",
  "function unpause()",
  "function asset() view returns (address)",
]

export default function ManagerPage() {
  const { connect, isHyper } = useWallet()
  const [asset, setAsset] = useState("")
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

  async function deploy() {
    setDeployErr(null); setDeployMsg(null)
    try {
      await connect()
      if (!isHyper) throw new Error("Please switch to Hyper Testnet (chain 998)")
      // fetch artifact from backend
      const r = await fetch(`${BACKEND_URL}/api/v1/artifacts/vault`)
      const art = await r.json()
      if (!art?.bytecode || !art?.abi) throw new Error("Artifact not available")
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
      // optional: register for discovery
      try { await fetch(`${BACKEND_URL}/api/v1/register_deployment?vault=${addr}&asset=${asset}`, { method: 'POST' }) } catch {}
    } catch (e: any) {
      setDeployErr(e?.shortMessage || e?.message || String(e))
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

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <section className="py-12">
          <div className="container mx-auto px-4 grid gap-6 lg:grid-cols-2">
            <Card className="p-6 gradient-card border-border/40">
              <h2 className="text-lg font-semibold mb-4">Deploy New Vault</h2>
              <div className="space-y-3">
                <div>
                  <Label>Asset ERC20 Address</Label>
                  <Input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="0x..." />
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
        </section>
      </main>
      <Footer />
    </div>
  )
}
