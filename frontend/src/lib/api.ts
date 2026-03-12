const BASE = ""

/** API key for X-MDKB-Key auth header — set via setApiKey() */
let apiKey: string | null = null

/** Configure the API key for authenticated requests */
export function setApiKey(key: string | null) {
  apiKey = key
}

/** Get the currently configured API key */
export function getApiKey(): string | null {
  return apiKey
}

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

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
    headers["X-MDKB-Key"] = apiKey
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
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) => request<T>("POST", path, body, signal),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
}
