export interface PluginEndpoint {
  method: string
  path: string
  description: string
}

export interface ConfigFieldSchema {
  type: string
  default: unknown
  label?: string
  description?: string
  min?: number
  max?: number
  options?: { value: string; label: string }[]
}

export interface SystemDependency {
  name: string
  binary: string
  required: boolean
  available: boolean
  install_hint: string
}

export interface PluginInfo {
  name: string
  display_name: string
  description: string
  version: string
  author: string
  icon: string
  category: string
  feature_flag: string
  enabled: boolean
  source: string
  error: string | null
  endpoints: PluginEndpoint[]
  config_schema: Record<string, ConfigFieldSchema>
  config: Record<string, unknown>
  requires: string[]
  has_manifest: boolean
  system_dependencies: SystemDependency[]
  dependencies_met: boolean
}

export interface CoreFeature {
  name: string
  display_name: string
  description: string
  icon: string
  category: string
  section: "core" | "mcp"
  enabled: boolean
}
