/**
 * Reusable polling helper for async operations with progress tracking
 */

import { api } from "@/lib/api"

/**
 * Like setInterval but pauses when the browser tab is hidden.
 * Returns a cleanup function that stops the interval and removes the listener.
 */
export function setVisibilityInterval(callback: () => void, ms: number): () => void {
  let id: ReturnType<typeof setInterval> | null = setInterval(callback, ms)

  const onVisibility = () => {
    if (document.hidden) {
      if (id !== null) { clearInterval(id); id = null }
    } else {
      if (id === null) { callback(); id = setInterval(callback, ms) }
    }
  }

  document.addEventListener("visibilitychange", onVisibility)

  return () => {
    if (id !== null) clearInterval(id)
    document.removeEventListener("visibilitychange", onVisibility)
  }
}

export interface PollingStatus {
  running: boolean
  progress: number
  message: string
  result: string
}

export interface PollingCallbacks {
  onProgress: (status: PollingStatus) => void
  onComplete: (result: string) => void
  onError: (error: Error) => void
}

/**
 * Start polling an endpoint until the operation completes
 * @param statusEndpoint - Endpoint to poll for status
 * @param interval - Polling interval in milliseconds (default: 1500ms)
 * @param callbacks - Callbacks for progress, completion, and errors
 * @returns Cleanup function to stop polling
 */
export function startPolling(
  statusEndpoint: string,
  interval: number,
  callbacks: PollingCallbacks,
): () => void {
  let stopped = false

  const stop = () => {
    if (!stopped) { stopped = true; cleanup() }
  }

  const poll = async () => {
    if (stopped) return
    try {
      const status = await api.get<PollingStatus>(statusEndpoint)
      if (stopped) return

      if (status.running) {
        callbacks.onProgress(status)
      } else {
        stop()
        callbacks.onComplete(status.result || "Operation complete")
      }
    } catch (error) {
      stop()
      callbacks.onError(error as Error)
    }
  }

  // Start polling (pauses when tab is hidden)
  const cleanup = setVisibilityInterval(poll, interval)

  return stop
}
