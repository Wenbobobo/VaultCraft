"use client"

import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { AlertCircle } from "lucide-react"

interface DepositModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  vault: {
    name: string
    unitNav: number
    lockDays: number
    performanceFee: number
  }
}

export function DepositModal({ open, onOpenChange, vault }: DepositModalProps) {
  const [amount, setAmount] = useState("")

  const estimatedShares = amount ? (Number.parseFloat(amount) / vault.unitNav).toFixed(2) : "0.00"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deposit to {vault.name}</DialogTitle>
          <DialogDescription>
            Enter the amount you wish to deposit. Your shares will be calculated based on the current NAV.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="amount">Deposit Amount (USDC)</Label>
            <Input
              id="amount"
              type="number"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>

          <div className="rounded-lg bg-muted/50 p-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Current NAV</span>
              <span className="font-mono font-semibold">${vault.unitNav.toFixed(3)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Estimated Shares</span>
              <span className="font-mono font-semibold">{estimatedShares}</span>
            </div>
          </div>

          <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 flex gap-3">
            <AlertCircle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
            <div className="text-sm space-y-1">
              <p className="font-medium text-warning">Lock Period: {vault.lockDays} day(s)</p>
              <p className="text-muted-foreground">
                Your deposit will be locked for {vault.lockDays} day(s) before you can withdraw.
              </p>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">
            Cancel
          </Button>
          <Button onClick={() => onOpenChange(false)} className="flex-1">
            Confirm Deposit
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
