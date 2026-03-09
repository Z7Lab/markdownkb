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
  scopeIds?: string | null,
  adHocTags?: string[] | null,
): AbortController {
  const controller = new AbortController()

  const body: Record<string, unknown> = { message }
  if (threadId) body.thread_id = threadId
  if (scopeIds) body.scope_ids = scopeIds
  if (adHocTags && adHocTags.length > 0) body.ad_hoc_tags = adHocTags

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

export interface PlanCallbacks {
  onStatus: (phase: string, message: string) => void
  onApproach: (content: string, score: number) => void
  onPlan: (plan: string) => void
  onSources: (sources: string[]) => void
  onTree: (tree: Record<string, unknown>) => void
  onReviews: (reviews: Record<string, unknown>[], refinedPlan: string) => void
  onDone: () => void
  onError: (error: Error) => void
}

export function streamPlan(
  request: string,
  callbacks: PlanCallbacks,
  options?: { iterations?: number; n_approaches?: number; skill_names?: string[]; scope_ids?: string | null; ad_hoc_tags?: string[] | null },
): AbortController {
  const controller = new AbortController()

  const body: Record<string, unknown> = { request }
  if (options?.iterations) body.iterations = options.iterations
  if (options?.n_approaches) body.n_approaches = options.n_approaches
  if (options?.skill_names) body.skill_names = options.skill_names
  if (options?.scope_ids) body.scope_ids = options.scope_ids
  if (options?.ad_hoc_tags && options.ad_hoc_tags.length > 0) body.ad_hoc_tags = options.ad_hoc_tags

  fetch("/api/planner/plan/stream", {
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
        if (event === "status") {
          callbacks.onStatus(data.phase as string, data.message as string)
        } else if (event === "approach") {
          callbacks.onApproach(data.content as string, data.score as number)
        } else if (event === "plan") {
          callbacks.onPlan(data.plan as string)
        } else if (event === "sources") {
          callbacks.onSources(data.sources as string[])
        } else if (event === "tree") {
          callbacks.onTree(data.tree as Record<string, unknown>)
        } else if (event === "reviews") {
          callbacks.onReviews(
            data.reviews as Record<string, unknown>[],
            data.refined_plan as string,
          )
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

export function streamSearchSummary(
  query: string,
  callbacks: SummaryCallbacks,
  options?: { top_k?: number; folder?: string | null; tag?: string | null; search_id?: string | null; scope_ids?: string | null; ad_hoc_tags?: string[] | null },
): AbortController {
  const controller = new AbortController()

  const body: Record<string, unknown> = { query }
  if (options?.top_k) body.top_k = options.top_k
  if (options?.folder) body.folder = options.folder
  if (options?.tag) body.tag = options.tag
  if (options?.search_id) body.search_id = options.search_id
  if (options?.scope_ids) body.scope_ids = options.scope_ids
  if (options?.ad_hoc_tags && options.ad_hoc_tags.length > 0) body.ad_hoc_tags = options.ad_hoc_tags

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
