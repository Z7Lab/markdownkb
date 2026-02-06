const BASE = ""

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
  const opts: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
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
      return res.json()
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

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) => request<T>("POST", path, body, signal),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
}
