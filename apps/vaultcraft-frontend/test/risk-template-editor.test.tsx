import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"

import { RiskTemplateEditor } from "@/components/risk-template-editor"

describe("RiskTemplateEditor", () => {
  const backendUrl = "http://backend"
  const vaultId = "0xabc"
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("loads current override and saves updates", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        base: { minLeverage: 1, maxLeverage: 5, allowedSymbols: "BTC,ETH" },
        effective: { minLeverage: 2, maxLeverage: 5, allowedSymbols: "BTC,ETH" },
        override: { minLeverage: 2, maxNotionalUsd: 5000, allowedSymbols: "BTC" },
      }),
    })
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        base: { minLeverage: 1, maxLeverage: 5, allowedSymbols: "BTC,ETH" },
        effective: { minLeverage: 3, maxLeverage: 5, allowedSymbols: "BTC,ETH" },
        override: { minLeverage: 3 },
      }),
    })

    render(<RiskTemplateEditor vaultId={vaultId} backendUrl={backendUrl} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const minInput = await screen.findByLabelText("最小杠杆")
    expect(minInput).toHaveValue("2")
    fireEvent.change(minInput, { target: { value: "3" } })

    fireEvent.click(screen.getByRole("button", { name: "保存风险模板" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const saveCall = fetchMock.mock.calls[1]
    expect(saveCall[0]).toBe(`${backendUrl}/api/v1/vaults/${vaultId}/risk`)
    expect(saveCall[1]?.method).toBe("PUT")
    expect(JSON.parse(String(saveCall[1]?.body))).toMatchObject({ minLeverage: 3 })
  })

  it("resets override to defaults", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ base: {}, effective: {}, override: {} }),
    })

    render(<RiskTemplateEditor vaultId={vaultId} backendUrl={backendUrl} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole("button", { name: "恢复平台默认" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const resetCall = fetchMock.mock.calls[1]
    expect(JSON.parse(String(resetCall[1]?.body))).toEqual({})
  })
})
