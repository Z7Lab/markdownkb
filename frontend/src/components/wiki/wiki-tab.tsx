import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { WikiCompileDialog } from "./wiki-compile-dialog"
import { EmptyHero } from "@/components/ui/empty-hero"
import { AppSidebar } from "@/components/ui/app-sidebar"
import {
  BookOpen, FileText, Clock, Loader2, Plus, Trash2, RefreshCw, ScrollText, GitBranch, Archive, ClipboardCheck,
} from "lucide-react"
import { WikiLintDialog } from "./wiki-lint-dialog"
import { relativeTime, cn } from "@/lib/utils"

interface WikiRecord {
  id: string
  name: string
  path: string
  page_count: number
  last_ingest_at: string | null
  created_at: string
}

interface CreateWikiResponse extends WikiRecord {
  docker_restart_required: boolean
}

interface FileEntry {
  path: string
  status?: string
  size?: number
  modified?: number
}

type DetailView = "index" | "log" | "pages"

export function WikiTab() {
  const [wikis, setWikis] = useState<WikiRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<DetailView>("index")

  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<WikiRecord | null>(null)
  const [compileOpen, setCompileOpen] = useState(false)
  const [lintOpen, setLintOpen] = useState(false)
  const [viewingFile, setViewingFile] = useState<string | null>(null)
  const [lintEnabled, setLintEnabled] = useState<boolean | null>(null)

  useEffect(() => {
    api.get<{ plugins_enabled?: Record<string, boolean> }>("/api/v1/settings")
      .then((r) => setLintEnabled(!!r.plugins_enabled?.lint))
      .catch(() => setLintEnabled(false))
  }, [])

  const loadWikis = useCallback(() => {
    api.get<{ wikis: WikiRecord[] }>("/api/v1/wiki-compile/wikis")
      .then((r) => {
        setWikis(r.wikis)
        setError(null)
        setSelected((prev) => prev ?? r.wikis[0]?.name ?? null)
      })
      .catch((err) => setError((err as Error).message))
  }, [])

  useEffect(() => {
    loadWikis()
  }, [loadWikis])

  const selectedWiki = useMemo(
    () => wikis?.find((w) => w.name === selected) ?? null,
    [wikis, selected],
  )

  async function handleCreate() {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    try {
      const r = await api.post<CreateWikiResponse>("/api/v1/wiki-compile/wikis", { name })
      if (r.docker_restart_required) {
        toast.warning("Wiki created — Docker restart required to mount the path before ingest.")
      } else {
        toast.success(`Wiki "${r.name}" created.`)
      }
      setNewName("")
      setCreateOpen(false)
      setSelected(r.name)
      loadWikis()
    } catch (err) {
      toast.error(`Create failed: ${(err as Error).message}`)
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(wiki: WikiRecord) {
    try {
      await api.del(`/api/v1/wiki-compile/wikis/${encodeURIComponent(wiki.name)}`)
      toast.success(`Wiki "${wiki.name}" deregistered (files kept on disk)`)
      setPendingDelete(null)
      if (selected === wiki.name) setSelected(null)
      loadWikis()
    } catch (err) {
      toast.error(`Delete failed: ${(err as Error).message}`)
    }
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <p className="text-sm text-destructive">Could not load wikis: {error}</p>
      </div>
    )
  }

  if (wikis === null) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground gap-1.5">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading wikis...
      </div>
    )
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <AppSidebar
        header={
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-muted-foreground flex items-center gap-1.5">
              <BookOpen className="h-4 w-4" />
              Wikis
            </h3>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={loadWikis}
              aria-label="Refresh wikis"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        }
      >
        <div className="p-2 space-y-0.5">
          {wikis.map((w) => (
            <button
              key={w.id}
              type="button"
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm hover:bg-accent",
                selected === w.name && "bg-accent font-medium",
              )}
              onClick={() => { setSelected(w.name); setView("index") }}
            >
              <div className="flex items-center gap-1.5 mb-0.5">
                <BookOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate flex-1">{w.name}</span>
              </div>
              <div className="text-[11px] text-muted-foreground pl-5">
                {w.page_count} {w.page_count === 1 ? "page" : "pages"}
                {w.last_ingest_at && <> · {relativeTime(w.last_ingest_at)}</>}
              </div>
            </button>
          ))}

          {!createOpen && (
            <button
              type="button"
              className="w-full text-left rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent flex items-center gap-1.5"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              New wiki
            </button>
          )}

          {createOpen && (
            <div className="rounded-md border p-2 space-y-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newName.trim()) handleCreate()
                  if (e.key === "Escape") { setCreateOpen(false); setNewName("") }
                }}
                placeholder="research"
                className="h-7 text-xs"
                disabled={creating}
                autoFocus
              />
              <div className="flex gap-1.5 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={() => { setCreateOpen(false); setNewName("") }}
                  disabled={creating}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="h-6 text-xs"
                  onClick={handleCreate}
                  disabled={creating || !newName.trim()}
                >
                  {creating ? "..." : "Create"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </AppSidebar>

      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        {selectedWiki ? (
          <WikiDetail
            wiki={selectedWiki}
            view={view}
            onViewChange={setView}
            onIngest={() => setCompileOpen(true)}
            onDelete={() => setPendingDelete(selectedWiki)}
            onOpenFile={setViewingFile}
            lintEnabled={!!lintEnabled}
            onLint={() => setLintOpen(true)}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 gap-4 text-center">
            <EmptyHero
              icon={BookOpen}
              label={wikis.length === 0 ? "No wikis yet" : "Select a wiki"}
            />
            <p className="text-sm text-muted-foreground max-w-md">
              {wikis.length === 0
                ? "A wiki is a writable directory where mdkb synthesizes summary pages from source material. Create one to get started."
                : "Pick a wiki from the sidebar to browse its pages."}
            </p>
            {wikis.length === 0 && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4 mr-1.5" /> Create wiki
              </Button>
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null) }}
        title={pendingDelete ? `Delete wiki "${pendingDelete.name}"?` : ""}
        description={pendingDelete
          ? `Removes the wiki from mdkb's registry. Files on disk at ${pendingDelete.path} are preserved. You can re-register by creating a wiki with the same path.`
          : ""}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => { if (pendingDelete) handleDelete(pendingDelete) }}
      />

      {selectedWiki && (
        <WikiCompileDialog
          open={compileOpen}
          sourcePath={null}
          onClose={() => { setCompileOpen(false); loadWikis() }}
          defaultWiki={selectedWiki.name}
          pickSourcePath
        />
      )}

      <FileViewerDialog
        path={viewingFile}
        onClose={() => setViewingFile(null)}
      />

      {selectedWiki && (
        <WikiLintDialog
          open={lintOpen}
          onClose={() => setLintOpen(false)}
          targetWiki={selectedWiki.name}
          onOpenReport={setViewingFile}
        />
      )}
    </div>
  )
}


function WikiDetail({
  wiki, view, onViewChange, onIngest, onDelete, onOpenFile, lintEnabled, onLint,
}: {
  wiki: WikiRecord
  view: DetailView
  onViewChange: (v: DetailView) => void
  onIngest: () => void
  onDelete: () => void
  onOpenFile: (path: string) => void
  lintEnabled: boolean
  onLint: () => void
}) {
  return (
    <>
      <header className="shrink-0 border-b px-6 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              {wiki.name}
            </h2>
            <p className="text-xs text-muted-foreground font-mono truncate mt-0.5">{wiki.path}</p>
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1.5">
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                {wiki.page_count} {wiki.page_count === 1 ? "page" : "pages"}
              </span>
              {wiki.last_ingest_at ? (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  ingested {relativeTime(wiki.last_ingest_at)}
                </span>
              ) : (
                <span className="italic">no ingests yet</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {lintEnabled && (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5"
                onClick={onLint}
                title="Run tiered lint — flag contradictions, orphans, uncovered raw sources"
              >
                <ClipboardCheck className="h-3.5 w-3.5" />
                Run lint
              </Button>
            )}
            <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={onIngest}>
              <Plus className="h-3.5 w-3.5" />
              Ingest source
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onDelete}
              aria-label="Delete wiki"
              title="Deregister wiki (files preserved)"
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-1 mt-3">
          <ViewTab active={view === "index"} onClick={() => onViewChange("index")} icon={Archive} label="Index" />
          <ViewTab active={view === "log"} onClick={() => onViewChange("log")} icon={ScrollText} label="Log" />
          <ViewTab active={view === "pages"} onClick={() => onViewChange("pages")} icon={FileText} label="Pages" />
        </div>
      </header>

      <ScrollArea className="flex-1 min-h-0">
        {view === "index" && (
          <MarkdownView
            path={`${wiki.path}/index.md`}
            wikiBase={wiki.path}
            onOpenFile={onOpenFile}
            emptyHint="No index yet — ingest a source to populate this wiki."
          />
        )}
        {view === "log" && (
          <MarkdownView
            path={`${wiki.path}/log.md`}
            wikiBase={wiki.path}
            onOpenFile={onOpenFile}
            emptyHint="No log entries yet."
          />
        )}
        {view === "pages" && <PagesView wiki={wiki} onOpenFile={onOpenFile} />}
      </ScrollArea>
    </>
  )
}

function ViewTab({
  active, onClick, icon: Icon, label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ComponentType<{ className?: string }>
  label: string
}) {
  return (
    <button
      type="button"
      className={cn(
        "px-3 py-1.5 text-xs rounded-md flex items-center gap-1.5 hover:bg-accent",
        active ? "bg-accent font-medium" : "text-muted-foreground",
      )}
      onClick={onClick}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}

function MarkdownView({
  path, wikiBase, onOpenFile, emptyHint,
}: {
  path: string
  wikiBase: string
  onOpenFile: (path: string) => void
  emptyHint: string
}) {
  const [content, setContent] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    setContent(null)
    setMissing(false)
    api.get<{ content: string }>(`/api/v1/file?path=${encodeURIComponent(path)}`)
      .then((r) => setContent(r.content))
      .catch(() => setMissing(true))
  }, [path])

  const handleLinkClick = (href: string): boolean => {
    // Absolute URLs, hash anchors, and mailto — let the browser handle them.
    if (/^(https?:|mailto:|#)/.test(href)) return false
    // Relative markdown-ish path — open in the file viewer.
    const base = wikiBase.replace(/\/$/, "")
    const absolute = href.startsWith("/") ? href : `${base}/${href}`
    onOpenFile(absolute)
    return true
  }

  if (missing) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground italic">
        {emptyHint}
      </div>
    )
  }
  if (content === null) {
    return (
      <div className="p-6 text-xs text-muted-foreground flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading...
      </div>
    )
  }
  return (
    <div className="p-6 max-w-3xl">
      <Markdown onLinkClick={handleLinkClick}>{content}</Markdown>
    </div>
  )
}

function PagesView({ wiki, onOpenFile }: { wiki: WikiRecord; onOpenFile: (p: string) => void }) {
  const [files, setFiles] = useState<FileEntry[] | null>(null)
  const prefix = wiki.path.endsWith("/") ? wiki.path : `${wiki.path}/`

  useEffect(() => {
    setFiles(null)
    api.get<{ files: FileEntry[] }>("/api/v1/files")
      .then((r) => {
        const matches = r.files
          .filter((f) => f.path.startsWith(prefix))
          .filter((f) => !f.path.endsWith("/index.md") && !f.path.endsWith("/log.md"))
          .sort((a, b) => (b.modified ?? 0) - (a.modified ?? 0))
        setFiles(matches)
      })
      .catch(() => setFiles([]))
  }, [prefix])

  if (files === null) {
    return (
      <div className="p-6 text-xs text-muted-foreground flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading pages...
      </div>
    )
  }

  if (files.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground italic">
        No pages yet. Use <span className="font-medium">Ingest source</span> to add one.
      </div>
    )
  }

  return (
    <div className="p-4 max-w-3xl space-y-1">
      {files.map((f) => {
        const rel = f.path.slice(prefix.length)
        const isIndexed = f.status === "complete"
        return (
          <button
            key={f.path}
            type="button"
            className="w-full text-left rounded-md border px-3 py-2 hover:bg-accent transition-colors flex items-center gap-2"
            onClick={() => onOpenFile(f.path)}
          >
            <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="flex-1 text-sm font-mono truncate">{rel}</span>
            {isIndexed && (
              <Badge variant="outline" className="text-[10px] gap-1">
                <GitBranch className="h-2.5 w-2.5" />
                indexed
              </Badge>
            )}
          </button>
        )
      })}
    </div>
  )
}
