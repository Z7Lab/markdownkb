import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface ImportFormat {
  label: string
  extensions: string[]
  available: boolean
}

export interface ImportMethod {
  id: string
  label: string
  available: boolean
  reason: string | null
  accept?: string
  formats?: ImportFormat[]
  transcript_support?: boolean
  provider?: string
  model?: string
  model_ready?: boolean
}

/**
 * Shared source of truth for what the ingestion UI can offer. Backed by
 * react-query so the Import tab, the New-note button, and the IngestionPanel
 * all read one cached response from `GET /api/v1/import/capabilities`.
 */
export function useImportCapabilities() {
  const { data, isLoading } = useQuery({
    queryKey: ["import-capabilities"],
    queryFn: () => api.get<{ methods: ImportMethod[] }>("/api/v1/import/capabilities"),
    staleTime: 30_000,
  })
  const methods = data?.methods ?? null
  const find = (id: string) => methods?.find((m) => m.id === id) ?? null
  return { methods, loading: isLoading, find }
}
