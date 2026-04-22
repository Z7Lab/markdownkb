const BASE = ""

/**
 * API key for X-MarkdownKB-Key auth header — set once at app startup via setApiKey().
 * Stored as module-level state (not reactive) because it is configured before
 * React renders and does not change at runtime. SSE streaming reads it
 * synchronously via getApiKey(), which is safe under this assumption.
 */
let apiKey: string | null = null

/** Configure the API key for authenticated requests */
export function setApiKey(key: string | null) {
  apiKey = key
}

/** Get the currently configured API key */
export function getApiKey(): string | null {
  return apiKey
}

/** Callback invoked on any 401 response — allows the app shell to react (e.g. show setup banner). */
let onUnauthorized: (() => void) | null = null

export function setOnUnauthorized(cb: (() => void) | null) {
  onUnauthorized = cb
}

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Generic HTTP request with retry/backoff. The generic `T` is a trust-based
 * cast — callers assert the expected response shape, but no runtime validation
 * (Zod, Valibot, etc.) is performed. Accepted risk: the backend is co-deployed
 * and version-locked with this frontend, so contract drift is caught by
 * integration testing rather than per-call schema validation.
 */
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  retries = 3,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }
  if (apiKey) {
    headers["X-MarkdownKB-Key"] = apiKey
  }

  const opts: RequestInit = {
    method,
    headers,
  }
  if (body !== undefined) {
    opts.body = JSON.stringify(body)
  }
  if (signal) {
    opts.signal = signal
  }

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${BASE}${path}`, opts)
      if (!res.ok) {
        if (res.status === 401 && onUnauthorized) onUnauthorized()
        const text = await res.text()
        throw new Error(`${res.status}: ${text}`)
      }
      return await res.json()
    } catch (error) {
      // If it's a connection error and we have retries left, retry with backoff
      const isConnectionError = error instanceof TypeError &&
                               (error.message.includes("fetch") ||
                                error.message.includes("Failed to fetch"))

      if (isConnectionError && attempt < retries) {
        // Exponential backoff: 100ms, 200ms, 400ms
        const delay = 100 * Math.pow(2, attempt)
        await sleep(delay)
        continue
      }

      // Otherwise, throw the error
      throw error
    }
  }

  throw new Error("Max retries exceeded")
}

/**
 * Raw HTTP request for non-JSON responses (blobs, streams, FormData uploads).
 * Injects auth header and checks status, but returns the raw Response for the
 * caller to consume. Used by api.upload (FormData → JSON) and api.fetchRaw
 * (caller handles response body — e.g. blob download, SSE-adjacent reads).
 */
async function requestRaw(
  method: string,
  path: string,
  body?: BodyInit | null,
  extraHeaders?: Record<string, string>,
  signal?: AbortSignal,
): Promise<Response> {
  const headers: Record<string, string> = { ...extraHeaders }
  if (apiKey) headers["X-MarkdownKB-Key"] = apiKey
  const opts: RequestInit = { method, headers }
  if (body != null) opts.body = body
  if (signal) opts.signal = signal
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    if (res.status === 401 && onUnauthorized) onUnauthorized()
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res
}

/**
 * Retry an async operation with fixed-delay backoff.
 * Returns a cleanup function that cancels pending retries.
 * Used by hooks for initial data loading (settings, threads, files, etc.).
 */
export function retryWithBackoff(
  fn: () => Promise<boolean>,
  opts?: { maxRetries?: number; delay?: number },
): () => void {
  const maxRetries = opts?.maxRetries ?? 10
  const delay = opts?.delay ?? 2000
  let timer: ReturnType<typeof setTimeout> | null = null
  let cancelled = false
  let retryCount = 0

  const attempt = async () => {
    if (cancelled) return
    const success = await fn()
    if (!success && !cancelled && retryCount < maxRetries) {
      retryCount++
      timer = setTimeout(attempt, delay)
    }
  }

  attempt()

  return () => {
    cancelled = true
    if (timer) clearTimeout(timer)
  }
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>("GET", path, undefined, signal),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) => request<T>("POST", path, body, signal),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
  /** POST a FormData body and parse the JSON response. Use for file/archive uploads. */
  upload: <T>(path: string, body: FormData, signal?: AbortSignal): Promise<T> =>
    requestRaw("POST", path, body, undefined, signal).then(r => r.json() as Promise<T>),
  /** Send a request and return the raw Response for non-JSON consumption (blobs, streams). */
  fetchRaw: (
    method: string,
    path: string,
    body?: BodyInit | null,
    extraHeaders?: Record<string, string>,
    signal?: AbortSignal,
  ) => requestRaw(method, path, body, extraHeaders, signal),
}
