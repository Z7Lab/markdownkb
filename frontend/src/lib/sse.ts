import { getApiKey } from "@/lib/api"
import type { PlanNode, SkillReview } from "@/lib/types"

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
        } catch (err) {
          console.warn("Malformed SSE JSON, skipping event:", (err as Error).message)
          continue
        }
        onEvent(eventType, data)
      }
    }
  }
}

/** Type-safe helpers for extracting typed values from SSE data */
function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : []
}

/** Validate that a value looks like a PlanNode (has required fields) */
function isPlanNode(value: unknown): value is PlanNode {
  if (!value || typeof value !== "object") return false
  const obj = value as Record<string, unknown>
  return typeof obj.content === "string" && typeof obj.type === "string"
}

/** Validate that a value looks like a SkillReview (has required fields) */
function isSkillReview(value: unknown): value is SkillReview {
  if (!value || typeof value !== "object") return false
  const obj = value as Record<string, unknown>
  return typeof obj.skill_name === "string" && typeof obj.review === "string"
}

/**
 * Generic SSE streaming helper — handles fetch, error handling, and abort.
 * All three stream functions share this pattern.
 */
function streamSSE(
  url: string,
  body: Record<string, unknown>,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onDone: (data?: Record<string, unknown>) => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController()

  const headers: Record<string, string> = { "Content-Type": "application/json" }
  const key = getApiKey()
  if (key) headers["X-MarkdownKB-Key"] = key

  fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const reader = res.body?.getReader()
      if (!reader) throw new Error("No response body")

      let doneReceived = false
      await parseSSEStream(reader, (event, data) => {
        if (event === "done") {
          doneReceived = true
          onDone(data)
        } else {
          onEvent(event, data)
        }
      })
      if (!doneReceived) onDone()
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err)
      }
    })

  return controller
}

export interface SSECallbacks {
  onThread: (threadId: string, title: string) => void
  onToken: (content: string) => void
  onSources: (sources: string[], sourceMap?: Record<string, string>) => void
  onDone: (meta?: { provider?: string; model?: string }) => void
  onError: (error: Error) => void
}

export interface SummaryCallbacks {
  onToken: (delta: string) => void
  onSources: (sources: string[]) => void
  onStatus?: (phase: string, message: string, iteration?: number, totalIterations?: number) => void
  onDone: (meta?: { provider?: string; model?: string }) => void
  onError: (error: Error) => void
}

export function streamChat(
  message: string,
  callbacks: SSECallbacks,
  threadId?: string | null,
  scopeIds?: string | null,
  adHocTags?: string[] | null,
  bucketIds?: string | null,
  bucketFilePaths?: string[] | null,
): AbortController {
  const body: Record<string, unknown> = { message }
  if (threadId) body.thread_id = threadId
  if (scopeIds) body.scope_ids = scopeIds
  if (adHocTags && adHocTags.length > 0) body.ad_hoc_tags = adHocTags
  if (bucketIds) body.bucket_ids = bucketIds
  if (bucketFilePaths && bucketFilePaths.length > 0) body.bucket_file_paths = bucketFilePaths

  return streamSSE(
    "/api/v1/chat/stream",
    body,
    (event, data) => {
      if (event === "thread") {
        callbacks.onThread(asString(data.thread_id), asString(data.title))
      } else if (event === "token") {
        callbacks.onToken(asString(data.content))
      } else if (event === "sources") {
        const sourceMap = data.source_map && typeof data.source_map === "object"
          ? data.source_map as Record<string, string>
          : undefined
        callbacks.onSources(asStringArray(data.sources), sourceMap)
      }
    },
    (data) => callbacks.onDone(data ? { provider: data.provider as string, model: data.model as string } : undefined),
    callbacks.onError,
  )
}

export interface PlanCallbacks {
  onStatus: (phase: string, message: string) => void
  onApproach: (content: string, score: number) => void
  onPlan: (plan: string) => void
  onSources: (sources: string[]) => void
  onTree: (tree: PlanNode) => void
  onReviews: (reviews: SkillReview[], refinedPlan: string) => void
  onDone: () => void
  onError: (error: Error) => void
}

export function streamPlan(
  request: string,
  callbacks: PlanCallbacks,
  options?: { iterations?: number; n_approaches?: number; skill_names?: string[]; scope_ids?: string | null; ad_hoc_tags?: string[] | null; bucket_ids?: string | null },
): AbortController {
  const body: Record<string, unknown> = { request }
  if (options?.iterations) body.iterations = options.iterations
  if (options?.n_approaches) body.n_approaches = options.n_approaches
  if (options?.skill_names) body.skill_names = options.skill_names
  if (options?.scope_ids) body.scope_ids = options.scope_ids
  if (options?.ad_hoc_tags && options.ad_hoc_tags.length > 0) body.ad_hoc_tags = options.ad_hoc_tags
  if (options?.bucket_ids) body.bucket_ids = options.bucket_ids

  return streamSSE(
    "/api/v1/planner/plan/stream",
    body,
    (event, data) => {
      if (event === "status") {
        callbacks.onStatus(asString(data.phase), asString(data.message))
      } else if (event === "approach") {
        callbacks.onApproach(asString(data.content), asNumber(data.score))
      } else if (event === "plan") {
        callbacks.onPlan(asString(data.plan))
      } else if (event === "sources") {
        callbacks.onSources(asStringArray(data.sources))
      } else if (event === "tree") {
        if (isPlanNode(data.tree)) {
          callbacks.onTree(data.tree)
        }
      } else if (event === "reviews") {
        const reviews = Array.isArray(data.reviews)
          ? data.reviews.filter(isSkillReview)
          : []
        callbacks.onReviews(reviews, asString(data.refined_plan))
      }
    },
    callbacks.onDone,
    callbacks.onError,
  )
}

export function streamSearchSummary(
  query: string,
  callbacks: SummaryCallbacks,
  options?: { top_k?: number; search_id?: string | null; scope_ids?: string | null; ad_hoc_tags?: string[] | null; deep_research?: boolean; deep_research_iterations?: number },
): AbortController {
  const body: Record<string, unknown> = { query }
  if (options?.top_k) body.top_k = options.top_k
  if (options?.search_id) body.search_id = options.search_id
  if (options?.scope_ids) body.scope_ids = options.scope_ids
  if (options?.ad_hoc_tags && options.ad_hoc_tags.length > 0) body.ad_hoc_tags = options.ad_hoc_tags
  if (options?.deep_research) body.deep_research = true
  if (options?.deep_research_iterations) body.deep_research_iterations = options.deep_research_iterations

  return streamSSE(
    "/api/v1/search/summarize",
    body,
    (event, data) => {
      if (event === "token") {
        callbacks.onToken(asString(data.content))
      } else if (event === "sources") {
        callbacks.onSources(asStringArray(data.sources))
      } else if (event === "status" && callbacks.onStatus) {
        callbacks.onStatus(
          asString(data.phase),
          asString(data.message),
          typeof data.iteration === "number" ? data.iteration : undefined,
          typeof data.total_iterations === "number" ? data.total_iterations : undefined,
        )
      }
    },
    (data) => callbacks.onDone(data ? { provider: data.provider as string, model: data.model as string } : undefined),
    callbacks.onError,
  )
}
