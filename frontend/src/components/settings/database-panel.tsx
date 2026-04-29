import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { api } from "@/lib/api"
import { formatBytes } from "@/lib/utils"
import { toast } from "sonner"
import { Database, Trash2, RefreshCw, PackageMinus, ScanSearch } from "lucide-react"

interface DatabaseStats {
  chat_history: { path: string; size_bytes: number }
  search_history: { path: string; size_bytes: number }
  vector_database: {
    tracking_path: string
    chroma_path: string
    size_bytes: number
    indexed_files: number
    total_files: number
    total_chunks: number
    vector_count: number
    embedding_model: string
    data_directory: string
  }
  plugin_databases?: Array<{ name: string; path: string; size_bytes: number }>
}

interface MaintenancePreview {
  orphaned_chunks: number
  orphaned_chunk_sources: number
  orphaned_segment_dirs: number
  orphaned_segment_dirs_bytes: number
  vacuum_estimate_bytes: number
  total_reclaimable_bytes: number
}


export function DatabasePanel() {
  const [stats, setStats] = useState<DatabaseStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [preview, setPreview] = useState<MaintenancePreview | null>(null)
  const [pendingAction, setPendingAction] = useState<{
    type: "chats" | "searches" | "vectors"
    title: string
    description: string
  } | null>(null)

  const loadStats = useCallback(async () => {
    try {
      const res = await api.get<DatabaseStats>("/api/v1/settings/database-stats")
      setStats(res)
    } catch (err) {
      /* stats load is best-effort; panel will show empty state */
      void err
    }
  }, [])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  const handleClearChats = async () => {
    setLoading(true)
    try {
      await api.post("/api/v1/settings/database/clear-chats", {})
      toast.success("Chat history cleared")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to clear: ${(err as Error).message}`)
    } finally {
      setLoading(false)
      setPendingAction(null)
    }
  }

  const handleClearSearches = async () => {
    setLoading(true)
    try {
      await api.post("/api/v1/settings/database/clear-searches", {})
      toast.success("Search history cleared")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to clear: ${(err as Error).message}`)
    } finally {
      setLoading(false)
      setPendingAction(null)
    }
  }

  const handleClearVectors = async () => {
    setLoading(true)
    try {
      await api.post("/api/v1/settings/database/clear-vectors", {})
      toast.success("Vector database cleared. You may want to reindex your files.")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to clear: ${(err as Error).message}`)
    } finally {
      setLoading(false)
      setPendingAction(null)
    }
  }

  const handleCompactChats = async () => {
    setLoading(true)
    try {
      await api.post("/api/v1/settings/database/compact-chats", {})
      toast.success("Chat database compacted")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to compact: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCompactSearches = async () => {
    setLoading(true)
    try {
      await api.post("/api/v1/settings/database/compact-searches", {})
      toast.success("Search database compacted")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to compact: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleScanVectors = async () => {
    setScanning(true)
    setPreview(null)
    try {
      const res = await api.get<MaintenancePreview>("/api/v1/settings/database/maintenance-preview")
      setPreview(res)
    } catch (err) {
      toast.error(`Scan failed: ${(err as Error).message}`)
    } finally {
      setScanning(false)
    }
  }

  const handleCleanupOrphans = async () => {
    setLoading(true)
    try {
      const res = await api.post<{ deleted_chunks: number; deleted_files: number }>(
        "/api/v1/settings/database/cleanup-orphans", {}
      )
      if (res.deleted_chunks > 0) {
        toast.success(`Removed ${res.deleted_chunks} orphaned chunks from ${res.deleted_files} deleted files`)
      } else {
        toast.success("No orphaned chunks found")
      }
      setPreview(null)
      await loadStats()
    } catch (err) {
      toast.error(`Cleanup failed: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCompactVectors = async () => {
    setLoading(true)
    try {
      const res = await api.post<{
        deleted_segment_dirs: number
        segment_dirs_freed_bytes: number
        vacuum_success: boolean
        vacuum_freed_bytes: number
        total_freed_bytes: number
        is_docker: boolean
      }>("/api/v1/settings/database/compact-vectors", {})
      const parts: string[] = []
      if (res.deleted_segment_dirs > 0)
        parts.push(`${res.deleted_segment_dirs} orphaned segment dir${res.deleted_segment_dirs !== 1 ? "s" : ""} deleted`)
      if (res.vacuum_success)
        parts.push(`${formatBytes(res.vacuum_freed_bytes)} reclaimed by VACUUM`)
      if (parts.length) {
        toast.success(parts.join(", "))
      } else if (!res.vacuum_success) {
        toast.info("Nothing compacted — VACUUM couldn't acquire an exclusive lock.")
      } else {
        toast.success("Compaction complete")
      }
      if (!res.vacuum_success) {
        const cmd = res.is_docker ? "`make docker-restart`" : "restarting the app"
        toast.warning(
          `VACUUM requires no active database writes. If it keeps failing, try ${cmd} to force it.`,
          { duration: 8000 }
        )
      }
      setPreview(null)
      await loadStats()
    } catch (err) {
      toast.error(`Compact failed: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  if (!stats) {
    return <div className="p-4 text-muted-foreground">Loading database stats...</div>
  }

  const hasIssues = preview && (preview.orphaned_chunks > 0 || preview.orphaned_segment_dirs > 0 || preview.vacuum_estimate_bytes > 0)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Database Maintenance</h2>
        <p className="text-sm text-muted-foreground">
          Manage and maintain your MarkdownKB databases
        </p>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Chat History
                </CardTitle>
                <CardDescription className="mt-1">
                  {stats.chat_history.path}
                </CardDescription>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">{formatBytes(stats.chat_history.size_bytes)}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Contains all conversation threads and messages
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() =>
                  setPendingAction({
                    type: "chats",
                    title: "Clear Chat History?",
                    description:
                      "This will permanently delete all conversation threads and messages. This action cannot be undone.",
                  })
                }
                disabled={loading}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Clear History
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCompactChats}
                disabled={loading}
                title="Reclaim disk space by removing deleted entries (runs SQLite VACUUM)"
              >
                <PackageMinus className="h-3.5 w-3.5 mr-1.5" />
                Compact Database
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Search History
                </CardTitle>
                <CardDescription className="mt-1">
                  {stats.search_history.path}
                </CardDescription>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">{formatBytes(stats.search_history.size_bytes)}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Contains saved searches and AI summaries
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() =>
                  setPendingAction({
                    type: "searches",
                    title: "Clear Search History?",
                    description:
                      "This will permanently delete all saved searches and summaries. This action cannot be undone.",
                  })
                }
                disabled={loading}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Clear History
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCompactSearches}
                disabled={loading}
                title="Reclaim disk space by removing deleted entries (runs SQLite VACUUM)"
              >
                <PackageMinus className="h-3.5 w-3.5 mr-1.5" />
                Compact Database
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Vector Database
                </CardTitle>
                <CardDescription className="mt-1.5">
                  {stats.vector_database.data_directory}
                </CardDescription>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">{formatBytes(stats.vector_database.size_bytes)}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-3">
              <div className="text-muted-foreground">Indexed files</div>
              <div>{stats.vector_database.indexed_files} / {stats.vector_database.total_files}</div>
              <div className="text-muted-foreground">Chunks</div>
              <div>{stats.vector_database.total_chunks.toLocaleString()}</div>
              <div className="text-muted-foreground">Vectors</div>
              <div>{stats.vector_database.vector_count.toLocaleString()}</div>
              <div className="text-muted-foreground">Embedding model</div>
              <div>{stats.vector_database.embedding_model}</div>
            </div>

            {/* Maintenance scan */}
            <div className="border-t pt-3 mt-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium">Maintenance</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleScanVectors}
                  disabled={scanning || loading}
                >
                  <ScanSearch className="h-3.5 w-3.5 mr-1.5" />
                  {scanning ? "Scanning…" : "Scan"}
                </Button>
              </div>

              {preview && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-muted-foreground">
                    <div>Orphaned chunks</div>
                    <div className={preview.orphaned_chunks > 0 ? "text-foreground font-medium" : ""}>
                      {preview.orphaned_chunks > 0
                        ? `${preview.orphaned_chunks.toLocaleString()} (${preview.orphaned_chunk_sources} files)`
                        : "None"}
                    </div>
                    <div>Orphaned segment dirs</div>
                    <div className={preview.orphaned_segment_dirs > 0 ? "text-foreground font-medium" : ""}>
                      {preview.orphaned_segment_dirs > 0
                        ? `${preview.orphaned_segment_dirs} (${formatBytes(preview.orphaned_segment_dirs_bytes)})`
                        : "None"}
                    </div>
                    <div>VACUUM estimate</div>
                    <div className={preview.vacuum_estimate_bytes > 0 ? "text-foreground font-medium" : ""}>
                      {preview.vacuum_estimate_bytes > 0
                        ? `~${formatBytes(preview.vacuum_estimate_bytes)}`
                        : "None"}
                    </div>
                    {hasIssues && (
                      <>
                        <div className="font-medium text-foreground">Total reclaimable</div>
                        <div className="font-medium text-foreground">
                          ~{formatBytes(preview.total_reclaimable_bytes)}
                        </div>
                      </>
                    )}
                  </div>

                  {hasIssues ? (
                    <div className="flex gap-2 mt-3">
                      {preview.orphaned_chunks > 0 && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCleanupOrphans}
                          disabled={loading}
                        >
                          <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                          Cleanup Orphans
                        </Button>
                      )}
                      {(preview.orphaned_segment_dirs > 0 || preview.vacuum_estimate_bytes > 0) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCompactVectors}
                          disabled={loading}
                          title="Delete orphaned segment directories and VACUUM chroma.sqlite3"
                        >
                          <PackageMinus className="h-3.5 w-3.5 mr-1.5" />
                          Compact Vector DB
                        </Button>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground mt-1">
                      Vector database is clean — nothing to reclaim.
                    </p>
                  )}
                </div>
              )}

              {!preview && !scanning && (
                <p className="text-xs text-muted-foreground">
                  Scan to check for orphaned chunks and reclaimable disk space.
                </p>
              )}
            </div>

            <div className="border-t pt-3 mt-3">
              <p className="text-xs text-muted-foreground mb-3">
                To back up, copy the entire <code className="bg-muted px-1 rounded">{stats.vector_database.data_directory}</code> directory.
              </p>
              <Button
                variant="destructive"
                size="sm"
                onClick={() =>
                  setPendingAction({
                    type: "vectors",
                    title: "Clear Vector Database?",
                    description:
                      "This will permanently delete BOTH the vector embeddings (chromadb) AND the file tracking database (markdownkb.db). These databases are interdependent and must be cleared together to maintain consistency. You will need to reindex your files afterward. This action cannot be undone.",
                  })
                }
                disabled={loading}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Clear Vector Database
              </Button>
            </div>
          </CardContent>
        </Card>

        {stats.plugin_databases && stats.plugin_databases.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Database className="h-4 w-4" />
                Plugin Databases
              </CardTitle>
              <CardDescription>Plugin-owned databases stored alongside core data</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {stats.plugin_databases.map((db) => (
                  <div key={db.name} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground font-mono">{db.name}.db</span>
                    <span className="font-medium">{formatBytes(db.size_bytes)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadStats}
            disabled={loading}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Refresh Stats
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={!!pendingAction}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null)
        }}
        title={pendingAction?.title || ""}
        description={pendingAction?.description || ""}
        confirmLabel="Clear Database"
        variant="destructive"
        onConfirm={() => {
          if (pendingAction?.type === "chats") handleClearChats()
          else if (pendingAction?.type === "searches") handleClearSearches()
          else if (pendingAction?.type === "vectors") handleClearVectors()
        }}
      />
    </div>
  )
}
