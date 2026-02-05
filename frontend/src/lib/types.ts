export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface SearchResult {
  document: string
  metadata: Record<string, string>
  score: number
}

export interface TrackedFile {
  path: string
  source_root: string
  status: string
  chunk_count: number
  content_hash: string
  size: number
  modified: number
}

export interface Provider {
  name: string
  model: string
  api_base: string
}

export interface AppSettings {
  active_provider: string
  providers: Provider[]
  features: Record<string, boolean>
  sources: string[]
  active_model: string
  active_api_base: string
}
