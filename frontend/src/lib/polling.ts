/**
 * Reusable polling helper for async operations with progress tracking
 */

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
  let pollInterval: ReturnType<typeof setInterval> | null = null

  const poll = async () => {
    try {
      const response = await fetch(statusEndpoint)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const status: PollingStatus = await response.json()

      if (status.running) {
        callbacks.onProgress(status)
      } else {
        // Operation complete
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
        callbacks.onComplete(status.result || "Operation complete")
      }
    } catch (error) {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      callbacks.onError(error as Error)
    }
  }

  // Start polling
  pollInterval = setInterval(poll, interval)

  // Return cleanup function
  return () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }
}
