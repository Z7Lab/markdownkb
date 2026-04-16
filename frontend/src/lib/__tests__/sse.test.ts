import { describe, it, expect } from "vitest"
import { parseSSEStream } from "../sse"

/** Helper: create a ReadableStream from string chunks */
function streamFromChunks(chunks: string[]): ReadableStreamDefaultReader<Uint8Array> {
  const encoder = new TextEncoder()
  let index = 0
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index++]))
      } else {
        controller.close()
      }
    },
  })
  return stream.getReader()
}

describe("parseSSEStream", () => {
  it("parses event + data pairs", async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const reader = streamFromChunks([
      'event: token\ndata: {"content":"hello"}\n\n',
      'event: done\ndata: {}\n\n',
    ])

    await parseSSEStream(reader, (event, data) => {
      events.push({ event, data })
    })

    expect(events).toHaveLength(2)
    expect(events[0]).toEqual({ event: "token", data: { content: "hello" } })
    expect(events[1]).toEqual({ event: "done", data: {} })
  })

  it("handles data split across chunks", async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const reader = streamFromChunks([
      'event: token\ndata: {"con',
      'tent":"world"}\n\n',
    ])

    await parseSSEStream(reader, (event, data) => {
      events.push({ event, data })
    })

    expect(events).toHaveLength(1)
    expect(events[0]!.data).toEqual({ content: "world" })
  })

  it("skips malformed JSON data lines", async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const reader = streamFromChunks([
      'event: token\ndata: not-json\n\n',
      'event: token\ndata: {"ok":true}\n\n',
    ])

    await parseSSEStream(reader, (event, data) => {
      events.push({ event, data })
    })

    expect(events).toHaveLength(1)
    expect(events[0]!.data).toEqual({ ok: true })
  })

  it("handles empty stream", async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const reader = streamFromChunks([])

    await parseSSEStream(reader, (event, data) => {
      events.push({ event, data })
    })

    expect(events).toHaveLength(0)
  })

  it("parses sources array event", async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const reader = streamFromChunks([
      'event: sources\ndata: {"sources":["file1.md","file2.md"]}\n\n',
    ])

    await parseSSEStream(reader, (event, data) => {
      events.push({ event, data })
    })

    expect(events).toHaveLength(1)
    expect(events[0]!.event).toBe("sources")
    expect(events[0]!.data.sources).toEqual(["file1.md", "file2.md"])
  })
})
