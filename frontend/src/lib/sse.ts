/** Generic SSE stream reader — parses event/data lines from a ReadableStream. */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ""
  let eventType = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7)
      } else if (line.startsWith("data: ")) {
        let data: Record<string, unknown>
        try {
          data = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        onEvent(eventType, data)
      }
    }
  }
}

export interface SSECallbacks {
  onThread: (threadId: string, title: string) => void
  onToken: (content: string) => void
  onSources: (sources: string[]) => void
  onDone: () => void
  onError: (error: Error) => void
}

export interface SummaryCallbacks {
  onToken: (delta: string) => void
  onSources: (sources: string[]) => void
  onDone: () => void
  onError: (error: Error) => void
}

export function streamChat(
  message: string,
  callbacks: SSECallbacks,
  threadId?: string | null,
): AbortController {
  const controller = new AbortController()

  const body: Record<string, string> = { message }
  if (threadId) {
    body.thread_id = threadId
  }

  fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const reader = res.body?.getReader()
      if (!reader) throw new Error("No response body")

      let doneReceived = false
      await parseSSEStream(reader, (event, data) => {
        if (event === "thread") {
          callbacks.onThread(data.thread_id as string, (data.title as string) ?? "")
        } else if (event === "token") {
          callbacks.onToken(data.content as string)
        } else if (event === "sources") {
          callbacks.onSources(data.sources as string[])
        } else if (event === "done") {
          doneReceived = true
          callbacks.onDone()
        }
      })
      if (!doneReceived) {
        callbacks.onDone()
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err)
      }
    })

  return controller
}

export function streamSearchSummary(
  query: string,
  callbacks: SummaryCallbacks,
  options?: { top_k?: number; folder?: string | null; tag?: string | null; search_id?: string | null },
): AbortController {
  const controller = new AbortController()

  const body: Record<string, unknown> = { query }
  if (options?.top_k) body.top_k = options.top_k
  if (options?.folder) body.folder = options.folder
  if (options?.tag) body.tag = options.tag
  if (options?.search_id) body.search_id = options.search_id

  fetch("/api/search/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const reader = res.body?.getReader()
      if (!reader) throw new Error("No response body")

      let doneReceived = false
      await parseSSEStream(reader, (event, data) => {
        if (event === "token") {
          callbacks.onToken(data.content as string)
        } else if (event === "sources") {
          callbacks.onSources(data.sources as string[])
        } else if (event === "done") {
          doneReceived = true
          callbacks.onDone()
        }
      })
      if (!doneReceived) callbacks.onDone()
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err)
      }
    })

  return controller
}
