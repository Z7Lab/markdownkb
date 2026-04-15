import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { Scope } from "@/lib/types"

export function useScopes() {
  const [scopes, setScopes] = useState<Scope[]>([])
  const [selectedScopeId, setSelectedScopeId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<{ scopes: Scope[] }>("/api/v1/scopes")
      setScopes(res.scopes)
    } catch (err) {
      console.warn("Failed to load scopes:", (err as Error).message)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const createScope = useCallback(async (name: string, folders: string[], tags: string[] = [], excludePatterns: string[] = []) => {
    try {
      const res = await api.post<{ id: string }>("/api/v1/scopes", { name, folders, tags, exclude_patterns: excludePatterns })
      await refresh()
      return res.id
    } catch (err) {
      toast.error(`Failed to create scope: ${(err as Error).message}`)
      return null
    }
  }, [refresh])

  const updateScope = useCallback(async (id: string, name: string, folders: string[], tags: string[] = [], excludePatterns: string[] = []) => {
    try {
      await api.put(`/api/v1/scopes/${id}`, { name, folders, tags, exclude_patterns: excludePatterns })
      await refresh()
      return true
    } catch (err) {
      toast.error(`Failed to update scope: ${(err as Error).message}`)
      return false
    }
  }, [refresh])

  const deleteScope = useCallback(async (id: string) => {
    try {
      await api.del(`/api/v1/scopes/${id}`)
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
