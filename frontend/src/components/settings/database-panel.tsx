import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { Database, Trash2, RefreshCw } from "lucide-react"

interface DatabaseStats {
  chat_history: { path: string; size_bytes: number }
  search_history: { path: string; size_bytes: number }
  vector_database: { tracking_path: string; chroma_path: string; size_bytes: number }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

export function DatabasePanel() {
  const [stats, setStats] = useState<DatabaseStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [pendingAction, setPendingAction] = useState<{
    type: "chats" | "searches" | "vectors"
    title: string
    description: string
  } | null>(null)

  const loadStats = async () => {
    try {
      const res = await api.get<DatabaseStats>("/api/settings/database-stats")
      setStats(res)
    } catch (err) {
      console.error("Failed to load database stats:", err)
    }
  }

  useEffect(() => {
    loadStats()
  }, [])

  const handleClearChats = async () => {
    setLoading(true)
    try {
      await api.post("/api/settings/database/clear-chats", {})
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
      await api.post("/api/settings/database/clear-searches", {})
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
      await api.post("/api/settings/database/clear-vectors", {})
      toast.success("Vector database cleared. You may want to reindex your files.")
      await loadStats()
    } catch (err) {
      toast.error(`Failed to clear: ${(err as Error).message}`)
    } finally {
      setLoading(false)
      setPendingAction(null)
    }
  }

  if (!stats) {
    return <div className="p-4 text-muted-foreground">Loading database stats...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Database Maintenance</h2>
        <p className="text-sm text-muted-foreground">
          Manage and maintain your mdkb databases
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
              Clear Chat History
            </Button>
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
              Clear Search History
            </Button>
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
                <CardDescription className="mt-1.5 space-y-0.5">
                  <div>{stats.vector_database.tracking_path}</div>
                  <div>{stats.vector_database.chroma_path}</div>
                </CardDescription>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">{formatBytes(stats.vector_database.size_bytes)}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Contains vector embeddings and file tracking metadata (both databases are interdependent and must be cleared together)
            </p>
            <Button
              variant="destructive"
              size="sm"
              onClick={() =>
                setPendingAction({
                  type: "vectors",
                  title: "Clear Vector Database?",
                  description:
                    "This will permanently delete BOTH the vector embeddings (chromadb) AND the file tracking database (mdkb.db). These databases are interdependent and must be cleared together to maintain consistency. You will need to reindex your files afterward. This action cannot be undone.",
                })
              }
              disabled={loading}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Clear Vector Database
            </Button>
          </CardContent>
        </Card>

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
