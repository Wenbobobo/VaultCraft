import Link from 'next/link'

export default function VaultDetail({ params }: { params: { address: string } }) {
  const { address } = params
  const isPrivate = address.includes('2222') // demo heuristic

  return (
    <main className="space-y-6">
      <Link href="/" className="text-slate-400 hover:text-slate-200">← 返回</Link>
      <section className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xl font-semibold">Vault {address}</div>
            <div className="text-xs text-slate-400 uppercase">{isPrivate ? 'private' : 'public'}</div>
          </div>
          <div className="kpi">
            <div className="label">AUM</div>
            <div className="value">$1,250,000</div>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-6">
          <div className="kpi"><div className="label">Sharpe</div><div className="value">1.8</div></div>
          <div className="kpi"><div className="label">Max DD</div><div className="value">-22%</div></div>
          <div className="kpi"><div className="label">Lock</div><div className="value">1 day</div></div>
          <div className="kpi"><div className="label">Perf Fee</div><div className="value">10%</div></div>
        </div>
      </section>

      {!isPrivate && (
        <section className="card">
          <div className="mb-2 text-slate-300">持仓（公募可见）</div>
          <ul className="text-slate-200 list-disc pl-6">
            <li>USDC 60%</li>
            <li>PAXG 25%</li>
            <li>ETH-PERPS 15%</li>
          </ul>
        </section>
      )}

      <section className="card">
        <div className="mb-2 text-slate-300">{isPrivate ? 'NAV/PnL（私募：不展示持仓）' : 'NAV/PnL'}</div>
        <div className="h-40 rounded bg-slate-800/60 grid place-items-center text-slate-400">图表占位</div>
      </section>
    </main>
  )
}

