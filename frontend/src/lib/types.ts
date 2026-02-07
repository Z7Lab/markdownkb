export interface PaginatedResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  sources?: string[]
}

export interface SearchResult {
  document: string
  metadata: Record<string, string>
  score: number
}

export interface SavedSearch {
  id: string
  query: string
  folder: string | null
  tag: string | null
  summary: string | null
  created_at: string
}

export interface TrackedFile {
  path: string
  source_root: string
  status: string
  chunk_count: number
  content_hash: string
  file_size: number
  mtime: number
  include_rag: number
}

export interface Provider {
  name: string
  model: string
  api_base: string
}

export interface Thread {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface AppSettings {
  active_provider: string
  providers: Provider[]
  features: Record<string, boolean>
  mcp: Record<string, unknown>
  sources: string[]
  global_ignore: string[]
  active_model: string
  active_api_base: string
  system_prompt: string
  default_system_prompt: string
  search_summary_prompt: string
  default_search_summary_prompt: string
  embedding_model: string
  intelligent_search_enabled: boolean
  top_k: number
  default_top_k: number
  score_threshold: number
  default_score_threshold: number
  hybrid_search: boolean
  default_hybrid_search: boolean
  bm25_weight: number
  default_bm25_weight: number
}

export interface EmbeddingModel {
  model_id: string
  display_name: string
  dimensions: number
  max_seq_length: number
  description: string
  installed: boolean
}

export interface TestPromptResult {
  response: string
  model: string
  time_seconds: number
  tokens: {
    prompt: number | null
    completion: number | null
    total: number | null
  }
}

export interface ModelInfo {
  max_input_tokens?: number | null
  max_output_tokens?: number | null
  input_cost_per_token?: number | null
  output_cost_per_token?: number | null
  supports_vision?: boolean
  supports_function_calling?: boolean
  supports_response_schema?: boolean
  supports_pdf_input?: boolean
  litellm_provider?: string
  mode?: string
  error?: string
  ollama_details?: {
    family?: string
    parameter_size?: string
    quantization_level?: string
    format?: string
  }
}
