import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi } from "vitest"

import { ExecPanel } from "@/components/exec-panel"

const toastSpy = vi.fn()

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: toastSpy, dismiss: vi.fn(), toasts: [] }),
}))

const createResponse = (data: any, ok = true) => ({
  ok,
  json: async () => data,
})

describe("ExecPanel", () => {
  beforeEach(() => {
    toastSpy.mockReset()
  })

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it("surfaces risk hints and maps pretrade errors to user messages", async () => {
    const fetchMock = vi.fn(async (url: any) => {
      const target = String(url)
      if (target.includes("/api/v1/status")) {
        return createResponse({
          flags: {
            exec_min_notional_usd: 15,
            exec_min_leverage: 1,
            exec_max_leverage: 5,
          },
        })
      }
      if (target.includes("/api/v1/pretrade")) {
        return createResponse({ ok: false, error: "Order must have minimum value of $10" })
      }
      if (target.includes("/api/v1/exec")) {
        return createResponse({ ok: false })
      }
      return createResponse({ ok: true })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExecPanel vaultId="0xvault" />)

    await waitFor(() => expect(screen.getByText(/Min notional \$15/)).toBeInTheDocument())
    await userEvent.click(screen.getByRole("button", { name: /Open/i }))
    await waitFor(() =>
      expect(screen.getByTestId("exec-error")).toHaveTextContent("Notional below minimum ($10)"),
    )
    expect(toastSpy).not.toHaveBeenCalled()
  })

  it("maps ack errors and triggers destructive toast", async () => {
    const fetchMock = vi.fn(async (url: any, init?: RequestInit) => {
      const target = String(url)
      if (target.includes("/api/v1/status")) {
        return createResponse({
          flags: {
            exec_min_notional_usd: 10,
            exec_min_leverage: 1,
            exec_max_leverage: 5,
          },
        })
      }
      if (target.includes("/api/v1/pretrade")) {
        return createResponse({ ok: true })
      }
      if (target.includes("/api/v1/exec/open")) {
        expect(init?.method).toBe("POST")
        return createResponse({
          dry_run: false,
          payload: {
            ack: "Order must have minimum value of $10",
          },
        })
      }
      return createResponse({ ok: true })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExecPanel vaultId="0xvault" />)

    await waitFor(() => expect(screen.getByText(/Min notional \$10/)).toBeInTheDocument())
    await userEvent.click(screen.getByRole("button", { name: /Open/i }))
    await waitFor(() =>
      expect(screen.getByTestId("exec-error")).toHaveTextContent("Notional below minimum ($10)"),
    )
    expect(toastSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Execution warning",
        variant: "destructive",
      }),
    )
  })

  it("syncs symbol from parent prop", async () => {
    const fetchMock = vi.fn(async (url: any) => {
      if (String(url).includes("/api/v1/status")) {
        return createResponse({
          flags: {},
        })
      }
      if (String(url).includes("/api/v1/pretrade")) {
        return createResponse({ ok: true })
      }
      return createResponse({ ok: true })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ExecPanel vaultId="0xvault" activeSymbol="BTC" onSymbolChange={vi.fn()} />)
    await waitFor(() => expect(screen.getByDisplayValue("BTC")).toBeInTheDocument())
  })
})
