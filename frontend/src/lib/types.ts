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

export interface SearchSnippet {
  text: string
  score: number
  heading: string
}

export interface SearchResult {
  document: string
  metadata: Record<string, string>
  score: number
  snippets?: SearchSnippet[]
  chunk_count?: number
  score_min?: number
  score_max?: number
  score_avg?: number
}

export interface ScoreChange {
  path: string
  old_score: number
  new_score: number
  change: number
}

export interface SavedSearch {
  id: string
  query: string
  folder: string | null
  tag: string | null
  summary: string | null
  result_paths: string[]
  result_count: number | null
  parent_id: string | null
  last_viewed_at: string | null
  created_at: string
}

export interface SearchVersion {
  id: string
  query: string
  result_count: number | null
  summary: string | null
  created_at: string
  parent_id: string | null
}

export interface SearchResponse {
  results: SearchResult[]
  search_id: string
  query?: string
  folder?: string | null
  tag?: string | null
  summary?: string | null
  created_at?: string
  is_historical: boolean
  version_count?: number
  llm_offline?: boolean
}

export interface CompareResponse {
  stored_result_count: number
  current_result_count: number
  missing_files: string[]
  new_files: string[]
  score_changes: ScoreChange[]
  results_changed: boolean
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
  api_key: string
  temperature?: number | null
  max_tokens?: number | null
  num_ctx?: number | null
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
  log_level: string
  temperature: number
  max_tokens: number
  num_ctx: number | null
}

export interface LogEntry {
  timestamp: number
  level: string
  logger: string
  message: string
}

export interface EmbeddingModel {
  model_id: string
  display_name: string
  dimensions: number
  max_seq_length: number
  description: string
  installed: boolean
  local_path: string
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

// -- Planner --

export interface PlanNode {
  content: string
  type: string
  score: number
  visits: number
  sources: string[]
  children: PlanNode[]
}

export interface SkillReview {
  skill_name: string
  review: string
  issues: string[]
  approvals: string[]
}

export interface PlanResult {
  plan: string
  tree: PlanNode
  sources: string[]
  exploration_log: string[]
  user_patterns: string[]
  iterations: number
  reviews?: SkillReview[]
  refined_plan?: string
}

export interface SkillInfo {
  name: string
  description: string
  source: string
}

export interface SavedPlan {
  id: string
  title: string
  query: string
  created_at: string
}

export interface Scope {
  id: string
  name: string
  folders: string[]
  created_at: string
}

// -- Knowledge Graph --

export interface GraphNode {
  id: string
  label: string
  cluster_id: number
  chunk_count: number
  source_root: string
  tags: string[]
  headings: string[]
  word_cloud: Record<string, number>
}

export interface GraphEdge {
  source: string
  target: string
  weight: number
}

export interface EdgeDetail {
  source: string
  target: string
  source_chunks: number
  target_chunks: number
  pairs: {
    source_text: string
    target_text: string
    similarity: number
  }[]
}

export interface GraphCluster {
  id: number
  label: string
  doc_count: number
  word_cloud: Record<string, number>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  clusters: GraphCluster[]
  global_word_cloud: Record<string, number>
  stats: {
    doc_count: number
    chunk_count: number
    edge_count: number
  }
}

export interface ModelEntry {
  id: string
  label: string
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
