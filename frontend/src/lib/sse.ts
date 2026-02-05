export interface SSECallbacks {
  onThread: (threadId: string, title: string) => void
  onToken: (content: string) => void
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

      const decoder = new TextDecoder()
      let buffer = ""
      let doneReceived = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        let eventType = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7)
          } else if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6))
            if (eventType === "thread") {
              callbacks.onThread(data.thread_id, data.title ?? "")
            } else if (eventType === "token") {
              callbacks.onToken(data.content)
            } else if (eventType === "sources") {
              callbacks.onSources(data.sources)
            } else if (eventType === "done") {
              doneReceived = true
              callbacks.onDone()
            }
          }
        }
      }
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
