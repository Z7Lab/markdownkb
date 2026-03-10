import { describe, it, expect, vi, afterEach } from "vitest"
import { relativeTime, basename, dirname } from "../utils"

describe("relativeTime", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("returns 'just now' for timestamps less than a minute ago", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-03-09T12:00:30Z"))
    expect(relativeTime("2026-03-09T12:00:00Z")).toBe("just now")
  })

  it("returns minutes for timestamps less than an hour ago", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-03-09T12:05:00Z"))
    expect(relativeTime("2026-03-09T12:00:00Z")).toBe("5m ago")
  })

  it("returns hours for timestamps less than a day ago", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-03-09T15:00:00Z"))
    expect(relativeTime("2026-03-09T12:00:00Z")).toBe("3h ago")
  })

  it("returns days for timestamps less than 30 days ago", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-03-12T12:00:00Z"))
    expect(relativeTime("2026-03-09T12:00:00Z")).toBe("3d ago")
  })

  it("returns localized date for timestamps older than 30 days", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-05-01T12:00:00Z"))
    const result = relativeTime("2026-03-01T12:00:00Z")
    // Should be a date string, not relative
    expect(result).not.toContain("ago")
    expect(result).not.toBe("")
  })

  it("handles space-separated date format (SQLite style)", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-03-09T12:05:00Z"))
    expect(relativeTime("2026-03-09 12:00:00")).toBe("5m ago")
  })

  it("returns empty string for invalid dates", () => {
    expect(relativeTime("not-a-date")).toBe("")
  })
})

describe("basename", () => {
  it("extracts filename from path", () => {
    expect(basename("/home/user/docs/readme.md")).toBe("readme.md")
  })

  it("returns the string if no slashes", () => {
    expect(basename("readme.md")).toBe("readme.md")
  })

  it("handles trailing slash", () => {
    expect(basename("/home/user/docs/")).toBe("")
  })
})

describe("dirname", () => {
  it("extracts directory from path", () => {
    expect(dirname("/home/user/docs/readme.md")).toBe("/home/user/docs")
  })

  it("returns / for root-level file", () => {
    expect(dirname("/readme.md")).toBe("/")
  })

  it("returns / for bare filename", () => {
    expect(dirname("readme.md")).toBe("/")
  })
})
