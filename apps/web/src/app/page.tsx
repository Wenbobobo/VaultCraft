import Link from 'next/link'

type VaultPreview = {
  address: string
  name: string
  type: 'public' | 'private'
  aum: number
  sharpe?: number
  mdd?: number
}

const sample: VaultPreview[] = [
  { address: '0x1111...abcd', name: 'Public Momentum', type: 'public', aum: 1250000, sharpe: 1.8, mdd: -0.22 },
  { address: '0x2222...beef', name: 'Private KOL Alpha', type: 'private', aum: 870000, sharpe: 2.3, mdd: -0.15 },
]

function formatUsd(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export default function Home() {
  return (
    <main className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2">
        {sample.map((v) => (
          <Link key={v.address} href={`/vault/${encodeURIComponent(v.address)}`} className="card hover:ring-1 hover:ring-brand-500/40 transition">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-lg font-semibold">{v.name}</div>
                <div className="text-xs text-slate-400 uppercase">{v.type}</div>
              </div>
              <div className="text-sm text-slate-300">{v.address}</div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="kpi"><div className="label">AUM</div><div className="value">{formatUsd(v.aum)}</div></div>
              <div className="kpi"><div className="label">Sharpe</div><div className="value">{v.sharpe ?? '-'} </div></div>
              <div className="kpi"><div className="label">Max DD</div><div className="value">{v.mdd ? `${(v.mdd*100).toFixed(1)}%` : '-'} </div></div>
            </div>
          </Link>
        ))}
      </section>
    </main>
  )
}

