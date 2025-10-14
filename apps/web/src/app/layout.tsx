import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'VaultCraft',
  description: 'Public transparent + Private non-disclosed DeFi vaults',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <header className="mb-8 flex items-center justify-between">
            <h1 className="text-2xl font-bold">VaultCraft</h1>
            <nav className="text-slate-400">v0 • Demo</nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  )
}

