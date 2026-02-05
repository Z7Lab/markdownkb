export interface SSECallbacks {
  onToken: (content: string) => void
  onSources: (sources: string[]) => void
  onDone: () => void
  onError: (error: Error) => void
}

export function streamChat(message: string, callbacks: SSECallbacks): AbortController {
  const controller = new AbortController()

  fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
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
            if (eventType === "token") {
              callbacks.onToken(data.content)
            } else if (eventType === "sources") {
              callbacks.onSources(data.sources)
            } else if (eventType === "done") {
              callbacks.onDone()
            }
          }
        }
      }
      callbacks.onDone()
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err)
      }
    })

  return controller
}
