import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { startPolling, type PollingStatus } from "@/lib/polling"
import type { EmbeddingModel } from "@/lib/types"

const EMBEDDING_STATUS_ENDPOINT = "/api/settings/embedding-models/status"

/** Start polling the embedding-models/status endpoint */
function pollEmbeddingStatus(
  cleanupRef: React.MutableRefObject<(() => void) | null>,
  callbacks: {
    onProgress: (status: PollingStatus) => void
    onComplete: (result: string) => void
    onError: (error: Error) => void
  },
  interval = 1500,
) {
  cleanupRef.current?.()
  cleanupRef.current = startPolling(EMBEDDING_STATUS_ENDPOINT, interval, callbacks)
}

export function useEmbeddingSettings(reload: () => Promise<boolean>) {
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([])
  const [embeddingStatus, setEmbeddingStatus] = useState("")
  const [embeddingSwitching, setEmbeddingSwitching] = useState(false)
  const [indexStatus, setIndexStatus] = useState("")
  const pollCleanupRef = useRef<(() => void) | null>(null)

  const loadEmbeddingModels = useCallback(async () => {
    try {
      const res = await api.get<{ models: EmbeddingModel[]; active_model: string }>(
        "/api/settings/embedding-models",
      )
      setEmbeddingModels(res.models)
    } catch (err) {
      console.debug("Failed to load embedding models:", err)
    }
  }, [])

  const makeEmbeddingPollCallbacks = useCallback((
    onCompleteExtra?: () => void,
    defaultResult = "Operation complete",
  ) => ({
    onProgress: (status: PollingStatus) => {
      const pct = Math.round(status.progress * 100)
      setEmbeddingStatus(`[${pct}%] ${status.message}`)
    },
    onComplete: (result: string) => {
      pollCleanupRef.current = null
      setEmbeddingSwitching(false)
      setEmbeddingStatus(result || defaultResult)
      onCompleteExtra?.()
    },
    onError: () => {
      pollCleanupRef.current = null
      setEmbeddingSwitching(false)
      setEmbeddingStatus("Lost connection during operation")
    },
  }), [])

  // Check for background reindex on mount
  useEffect(() => {
    loadEmbeddingModels()

    api.get<PollingStatus>(EMBEDDING_STATUS_ENDPOINT).then((st) => {
      if (st.running) {
        setEmbeddingSwitching(true)
        const pct = Math.round(st.progress * 100)
        setEmbeddingStatus(`[${pct}%] ${st.message}`)
        pollEmbeddingStatus(pollCleanupRef, makeEmbeddingPollCallbacks(() => {
          reload()
          loadEmbeddingModels()
        }, "Reindex complete"))
      }
    }).catch((err) => { console.debug("Failed to check embedding status:", err) })

    return () => { pollCleanupRef.current?.() }
  }, [reload, loadEmbeddingModels, makeEmbeddingPollCallbacks])

  const reindex = useCallback(async (force = false) => {
    if (!force) {
      setIndexStatus("Indexing...")
      try {
        const res = await api.post<{ message: string }>("/api/index")
        setIndexStatus(res.message)
      } catch (e) {
        setIndexStatus(`Error: ${e}`)
      }
      return
    }

    setEmbeddingStatus("Force reindexing all files...")
    setEmbeddingSwitching(true)
    try {
      await api.post("/api/index", { force: true })
      pollEmbeddingStatus(pollCleanupRef, makeEmbeddingPollCallbacks(() => {
        reload()
      }, "Reindex complete"))
    } catch (e) {
      setEmbeddingSwitching(false)
      setEmbeddingStatus(`Error: ${e}`)
    }
  }, [reload, makeEmbeddingPollCallbacks])

  const cancelIndex = useCallback(async () => {
    await api.post("/api/index/cancel")
    pollCleanupRef.current?.()
    pollCleanupRef.current = null
    setEmbeddingSwitching(false)
    setEmbeddingStatus("Cancelled")
    setIndexStatus("Cancelled")
  }, [])

  const installEmbeddingModel = useCallback(
    async (modelId: string) => {
      setEmbeddingStatus(`Installing ${modelId}...`)
      setEmbeddingSwitching(true)
      try {
        const res = await api.post<{ status: string }>(
          "/api/settings/embedding-models/install",
          { model_id: modelId },
        )
        if (res.status === "already_installed") {
          setEmbeddingStatus(`${modelId} already installed`)
          setEmbeddingSwitching(false)
          await loadEmbeddingModels()
          return
        }
        pollEmbeddingStatus(pollCleanupRef, makeEmbeddingPollCallbacks(() => {
          loadEmbeddingModels()
        }, `Installed ${modelId}`), 1000)
      } catch (e) {
        setEmbeddingSwitching(false)
        setEmbeddingStatus(`Error: ${e}`)
      }
    },
    [loadEmbeddingModels, makeEmbeddingPollCallbacks],
  )

  const uninstallEmbeddingModel = useCallback(
    async (modelId: string) => {
      try {
        await api.post("/api/settings/embedding-models/uninstall", { model_id: modelId })
        setEmbeddingStatus(`Removed ${modelId}`)
        await loadEmbeddingModels()
      } catch (e) {
        setEmbeddingStatus(`Error: ${e}`)
      }
    },
    [loadEmbeddingModels],
  )

  const switchEmbeddingModel = useCallback(
    async (modelId: string) => {
      setEmbeddingStatus(`Switching to ${modelId}...`)
      setEmbeddingSwitching(true)
      try {
        await api.put<{ status: string }>(
          "/api/settings/embedding-models/switch",
          { model_id: modelId },
        )
        await loadEmbeddingModels()
        pollEmbeddingStatus(pollCleanupRef, makeEmbeddingPollCallbacks(() => {
          reload()
          loadEmbeddingModels()
        }, "Switched successfully"))
      } catch (e) {
        setEmbeddingSwitching(false)
        setEmbeddingStatus(`Error: ${e}`)
      }
    },
    [reload, loadEmbeddingModels, makeEmbeddingPollCallbacks],
  )

  return {
    embeddingModels,
    embeddingStatus,
    embeddingSwitching,
    indexStatus,
    reindex,
    cancelIndex,
    installEmbeddingModel,
    uninstallEmbeddingModel,
    switchEmbeddingModel,
  }
}
