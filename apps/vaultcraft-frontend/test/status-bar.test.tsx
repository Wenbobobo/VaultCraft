import { render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"

import { StatusBar } from "@/components/status-bar"
import { LocaleProvider } from "@/components/locale-provider"

const mockFetch = vi.fn()
let dateSpy: ReturnType<typeof vi.spyOn> | null = null

describe("StatusBar", () => {
  beforeEach(() => {
    dateSpy = vi.spyOn(Date, "now").mockReturnValue(new Date("2025-01-01T00:00:00Z").getTime())
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        flags: {
          enable_live_exec: false,
          enable_sdk: true,
          enable_user_ws: true,
          enable_snapshot_daemon: true,
          allowed_symbols: "BTC,ETH",
          exec_min_leverage: 1,
          exec_max_leverage: 5,
          exec_min_notional_usd: 10,
          risk_template: {
            allowedSymbols: "BTC,ETH",
            minLeverage: 1,
            maxLeverage: 5,
            minNotionalUsd: 10,
          },
        },
        network: { chainId: 998, block: 12345 },
        state: {
          listener: "running",
          snapshot: "running",
          listenerLastTs: Math.floor(Date.now() / 1000) - 90,
          lastAckTs: Math.floor(Date.now() / 1000) - 30,
        },
      }),
    })
    vi.stubGlobal("fetch", mockFetch)
  })

  afterEach(() => {
    dateSpy?.mockRestore()
    dateSpy = null
    vi.unstubAllGlobals()
    mockFetch.mockReset()
    vi.restoreAllMocks()
  })

  it("renders live ops information with ack fallback messaging", async () => {
    render(
      <LocaleProvider>
        <StatusBar />
      </LocaleProvider>,
    )

    await waitFor(() => expect(mockFetch).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText(/Mode/)).toBeInTheDocument())
    expect(screen.getByText("Mode:")).toBeInTheDocument()
    expect(screen.getByText(/Dry-run/i)).toBeInTheDocument()
    expect(screen.getByText(/Listener:/i)).toHaveTextContent("running · last 1m")
    expect(screen.getByText(/Ack:/i)).toHaveTextContent("last ack <1m")
    expect(screen.getByText(/Symbols:/i)).toHaveTextContent("BTC,ETH")
    expect(screen.getByText(/Lev/i)).toHaveTextContent("1–5x")
    expect(screen.getByText(/Risk:/i)).toBeInTheDocument()
  })
})
