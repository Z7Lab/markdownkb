import { describe, it, expect, vi, beforeEach } from "vitest"
import { api, setApiKey, getApiKey } from "../api"

describe("api", () => {
  const mockFetch = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    vi.stubGlobal("fetch", mockFetch)
    setApiKey(null)
  })

  function mockJsonResponse(data: unknown, status = 200) {
    mockFetch.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(data),
      text: () => Promise.resolve(JSON.stringify(data)),
    })
  }

  it("sends GET request", async () => {
    mockJsonResponse({ items: [] })
    const result = await api.get<{ items: unknown[] }>("/api/files")
    expect(result).toEqual({ items: [] })
    expect(mockFetch).toHaveBeenCalledWith("/api/files", expect.objectContaining({ method: "GET" }))
  })

  it("sends POST request with body", async () => {
    mockJsonResponse({ ok: true })
    await api.post("/api/files/index", { paths: ["/a.md"] })
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/files/index",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ paths: ["/a.md"] }),
      }),
    )
  })

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Not found"),
    })
    await expect(api.get("/api/missing")).rejects.toThrow("404: Not found")
  })

  describe("auth header", () => {
    it("does not include X-MDKB-Key when no key is set", async () => {
      mockJsonResponse({})
      await api.get("/api/test")
      const callArgs = mockFetch.mock.calls[0]
      expect(callArgs[1].headers["X-MDKB-Key"]).toBeUndefined()
    })

    it("includes X-MDKB-Key when key is set", async () => {
      setApiKey("test-key-123")
      mockJsonResponse({})
      await api.get("/api/test")
      const callArgs = mockFetch.mock.calls[0]
      expect(callArgs[1].headers["X-MDKB-Key"]).toBe("test-key-123")
    })

    it("getApiKey returns the current key", () => {
      expect(getApiKey()).toBeNull()
      setApiKey("my-key")
      expect(getApiKey()).toBe("my-key")
      setApiKey(null)
      expect(getApiKey()).toBeNull()
    })
  })

  describe("retry on connection error", () => {
    it("retries on fetch TypeError", async () => {
      mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"))
      mockJsonResponse({ ok: true })

      const result = await api.get<{ ok: boolean }>("/api/test")
      expect(result).toEqual({ ok: true })
      expect(mockFetch).toHaveBeenCalledTimes(2)
    })

    it("throws after max retries", async () => {
      // mockRejectedValue sets the default, so all calls will reject
      mockFetch.mockRejectedValue(new TypeError("Failed to fetch"))
      await expect(api.get("/api/test")).rejects.toThrow("Failed to fetch")
      // 1 initial + 3 retries = 4 calls
      expect(mockFetch).toHaveBeenCalledTimes(4)
    })
  })
})
