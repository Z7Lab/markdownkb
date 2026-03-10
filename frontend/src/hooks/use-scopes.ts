import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { Scope } from "@/lib/types"

export function useScopes() {
  const [scopes, setScopes] = useState<Scope[]>([])
  const [selectedScopeId, setSelectedScopeId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<{ scopes: Scope[] }>("/api/scopes")
      setScopes(res.scopes)
    } catch {
      // Silently fail on load — scopes are optional
    }
  }, [])

  useEffect(() => {
    refresh() // eslint-disable-line react-hooks/set-state-in-effect -- initial data fetch on mount
  }, [refresh])

  const createScope = useCallback(async (name: string, folders: string[], tags: string[] = []) => {
    try {
      const res = await api.post<{ id: string }>("/api/scopes", { name, folders, tags })
      await refresh()
      return res.id
    } catch (err) {
      toast.error(`Failed to create scope: ${(err as Error).message}`)
      return null
    }
  }, [refresh])

  const updateScope = useCallback(async (id: string, name: string, folders: string[], tags: string[] = []) => {
    try {
      await api.put(`/api/scopes/${id}`, { name, folders, tags })
      await refresh()
      return true
    } catch (err) {
      toast.error(`Failed to update scope: ${(err as Error).message}`)
      return false
    }
  }, [refresh])

  const deleteScope = useCallback(async (id: string) => {
    try {
      await api.del(`/api/scopes/${id}`)
      if (selectedScopeId === id) setSelectedScopeId(null)
      await refresh()
      return true
    } catch (err) {
      toast.error(`Failed to delete scope: ${(err as Error).message}`)
      return false
    }
  }, [refresh, selectedScopeId])

  return {
    scopes,
    selectedScopeId,
    setSelectedScopeId,
    createScope,
    updateScope,
    deleteScope,
    refresh,
  }
}
