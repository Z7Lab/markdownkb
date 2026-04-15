import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { startPolling } from "../polling"

describe("startPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  function mockFetchResponse(data: unknown) {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(data),
    } as Response)
  }

  it("calls onProgress while running", async () => {
    const onProgress = vi.fn()
    const onComplete = vi.fn()
    const onError = vi.fn()

    mockFetchResponse({ running: true, progress: 50, message: "Halfway", result: "" })

    startPolling("/api/v1/status", 1000, { onProgress, onComplete, onError })

    vi.advanceTimersByTime(1000)
    await vi.runAllTimersAsync()

    expect(onProgress).toHaveBeenCalledWith(
      expect.objectContaining({ running: true, progress: 50 }),
    )
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("calls onComplete when done", async () => {
    const onProgress = vi.fn()
    const onComplete = vi.fn()
    const onError = vi.fn()

    mockFetchResponse({ running: false, progress: 100, message: "Done", result: "Success" })

    startPolling("/api/v1/status", 1000, { onProgress, onComplete, onError })

    vi.advanceTimersByTime(1000)
    await vi.runAllTimersAsync()

    expect(onComplete).toHaveBeenCalledWith("Success")
  })

  it("calls onError on fetch failure", async () => {
    const onProgress = vi.fn()
    const onComplete = vi.fn()
    const onError = vi.fn()

    vi.mocked(fetch).mockRejectedValueOnce(new Error("Network error"))

    startPolling("/api/v1/status", 1000, { onProgress, onComplete, onError })

    vi.advanceTimersByTime(1000)
    await vi.runAllTimersAsync()

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "Network error" }))
  })

  it("returns cleanup function that stops polling", () => {
    mockFetchResponse({ running: true, progress: 0, message: "", result: "" })

    const cleanup = startPolling("/api/v1/status", 1000, {
      onProgress: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    })

    cleanup()
    vi.advanceTimersByTime(5000)

    // fetch should never have been called since we cleaned up before interval fired
    // Actually the first interval fires at 1000ms; we cleaned up immediately
    expect(fetch).not.toHaveBeenCalled()
  })
})
