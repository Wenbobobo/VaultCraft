import Link from 'next/link'
import dynamic from 'next/dynamic'

const VaultClient = dynamic(() => import('./vault.client'), { ssr: false })

export default function VaultDetail({ params }: { params: { address: string } }) {
  const { address } = params
  return (
    <main className="space-y-6">
      <Link href="/" className="text-slate-400 hover:text-slate-200">← 返回</Link>
      <VaultClient address={address} />
    </main>
  )
}
