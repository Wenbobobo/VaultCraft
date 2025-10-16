import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden gradient-hero py-24 md:py-32">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="mb-6 text-5xl font-bold tracking-tight text-balance md:text-6xl lg:text-7xl">
            Verifiable Trader <span className="text-primary">Vaults</span>
          </h1>

          <p className="mb-10 text-lg text-muted-foreground text-balance max-w-xl mx-auto leading-relaxed">
            Transparent performance. On-chain execution. Performance-based fees with high-water mark protection.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button size="lg" className="gap-2">
              Explore Vaults
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline">
              Connect Wallet
            </Button>
          </div>

          <div className="mt-20 grid grid-cols-3 gap-8 max-w-2xl mx-auto">
            <div className="text-center">
              <div className="text-3xl font-bold mb-1">$24.5M</div>
              <div className="text-sm text-muted-foreground">Total AUM</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold mb-1">156</div>
              <div className="text-sm text-muted-foreground">Active Vaults</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold mb-1">18.4%</div>
              <div className="text-sm text-muted-foreground">Avg Return</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
