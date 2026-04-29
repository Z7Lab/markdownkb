import { useState, useCallback, useMemo } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"
import { Loader2, Github, Check, AlertCircle, Search, X } from "lucide-react"
import { toast } from "sonner"

interface GithubFile {
  path: string
  sha: string
  isMdx: boolean
  selected: boolean
}

type Phase = "idle" | "loading" | "list" | "importing"

function parseGithubUrl(raw: string): { owner: string; repo: string; branch?: string; pathPrefix?: string } | null {
  try {
    const url = new URL(raw.trim())
    if (!url.hostname.includes("github.com")) return null
    // pathname: /owner/repo[/tree/branch[/path/to/folder]]
    const parts = url.pathname.replace(/^\//, "").split("/").filter(Boolean)
    if (parts.length < 2) return null
    const owner = parts[0]!
    const repo = parts[1]!.replace(/\.git$/, "")
    if (parts[2] === "tree" && parts.length >= 4) {
      const branch = parts[3]!
      const pathPrefix = parts.slice(4).join("/") || undefined
      return { owner, repo, branch, pathPrefix }
    }
    return { owner, repo }
  } catch {
    const match = /^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$/.exec(raw.trim())
    if (match) return { owner: match[1]!, repo: match[2]! }
    return null
  }
}

function stripMdx(content: string): string {
  return content
    .split("\n")
    .filter((line) => !/^import\s/.test(line) && !/^export\s/.test(line))
    .join("\n")
    .replace(/<([A-Z][A-Za-z0-9]*)[^>]*>[\s\S]*?<\/\1>/g, "")
    .replace(/<[A-Z][A-Za-z0-9]*[^>]*\/>/g, "")
    .trim()
}

/** Multi-term AND filter — same logic as the Files tab */
function pathMatches(path: string, filter: string): boolean {
  const lower = path.toLowerCase()
  return filter.toLowerCase().split(/\s+/).filter(Boolean).every((term) => lower.includes(term))
}

export function GithubImportDialog({
  open,
  onClose,
  onImport,
  onDone,
}: {
  open: boolean
  onClose: () => void
  onImport: (name: string, content: string) => Promise<void>
  onDone?: () => void
}) {
  const [repoUrl, setRepoUrl] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")
  const [files, setFiles] = useState<GithubFile[]>([])
  const [repoInfo, setRepoInfo] = useState<{ owner: string; repo: string; branch: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [importProgress, setImportProgress] = useState<{ done: number; total: number }>({ done: 0, total: 0 })
  const [filterText, setFilterText] = useState("")

  const visibleFiles = useMemo(
    () => filterText ? files.filter((f) => pathMatches(f.path, filterText)) : files,
    [files, filterText]
  )

  const selectedCount = useMemo(() => files.filter((f) => f.selected).length, [files])
  const mdxCount = useMemo(() => files.filter((f) => f.isMdx && f.selected).length, [files])

  const handleFetch = useCallback(async () => {
    const parsed = parseGithubUrl(repoUrl)
    if (!parsed) {
      setError("Enter a GitHub URL or owner/repo (e.g. github.com/user/repo or user/repo)")
      return
    }
    setError(null)
    setPhase("loading")
    setFilterText("")

    try {
      let branch = parsed.branch
      if (!branch) {
        const repoRes = await fetch(`https://api.github.com/repos/${parsed.owner}/${parsed.repo}`)
        if (!repoRes.ok) throw new Error(repoRes.status === 404 ? "Repository not found" : `GitHub API error: ${repoRes.status}`)
        const repoData = await repoRes.json() as { default_branch: string }
        branch = repoData.default_branch
      }

      const treeRes = await fetch(
        `https://api.github.com/repos/${parsed.owner}/${parsed.repo}/git/trees/${branch}?recursive=1`
      )
      if (!treeRes.ok) throw new Error(`Could not fetch repo tree: ${treeRes.status}`)
      const treeData = await treeRes.json() as { tree: { path: string; sha: string; type: string }[]; truncated?: boolean }

      if (treeData.truncated) {
        setError("Repository tree is too large for the GitHub API — only partial results available")
      }

      const prefix = parsed.pathPrefix ? parsed.pathPrefix.replace(/\/?$/, "/") : null

      const mdFiles = treeData.tree
        .filter((f) => f.type === "blob" && /\.(md|mdx)$/i.test(f.path) && (!prefix || f.path.startsWith(prefix)))
        .map((f) => ({
          path: f.path,
          sha: f.sha,
          isMdx: /\.mdx$/i.test(f.path),
          selected: true,
        }))

      if (mdFiles.length === 0) {
        setError("No .md or .mdx files found in this repository")
        setPhase("idle")
        return
      }

      setRepoInfo({ owner: parsed.owner, repo: parsed.repo, branch })
      setFiles(mdFiles)
      setPhase("list")
    } catch (err) {
      setError((err as Error).message)
      setPhase("idle")
    }
  }, [repoUrl])

  const toggleFile = useCallback((path: string) => {
    setFiles((prev) => prev.map((f) => f.path === path ? { ...f, selected: !f.selected } : f))
  }, [])

  const toggleAll = useCallback((selected: boolean) => {
    setFiles((prev) => prev.map((f) => ({ ...f, selected })))
  }, [])

  const toggleVisible = useCallback((selected: boolean) => {
    const visiblePaths = new Set(visibleFiles.map((f) => f.path))
    setFiles((prev) => prev.map((f) => visiblePaths.has(f.path) ? { ...f, selected } : f))
  }, [visibleFiles])

  const handleImport = useCallback(async () => {
    if (!repoInfo) return
    const selected = files.filter((f) => f.selected)
    if (selected.length === 0) return

    setPhase("importing")
    setImportProgress({ done: 0, total: selected.length })

    let succeeded = 0
    let failed = 0

    for (let i = 0; i < selected.length; i++) {
      const file = selected[i]!
      try {
        const rawUrl = `https://raw.githubusercontent.com/${repoInfo.owner}/${repoInfo.repo}/${repoInfo.branch}/${file.path}`
        const res = await fetch(rawUrl)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        let content = await res.text()
        if (file.isMdx) content = stripMdx(content)
        const name = file.path.replace(/\//g, "_").replace(/\.mdx?$/i, "") + ".md"
        await onImport(name, content)
        succeeded++
      } catch {
        failed++
      }
      setImportProgress({ done: i + 1, total: selected.length })
    }

    if (failed === 0) toast.success(`Imported ${succeeded} file${succeeded !== 1 ? "s" : ""} from GitHub`)
    else if (succeeded === 0) toast.error("All imports failed")
    else toast.warning(`${succeeded} imported, ${failed} failed`)

    onDone?.()
    onClose()
    setRepoUrl("")
    setFiles([])
    setRepoInfo(null)
    setFilterText("")
    setPhase("idle")
  }, [repoInfo, files, onImport, onClose, onDone])

  const closeAndReset = useCallback(() => {
    onClose()
    setPhase("idle")
    setFiles([])
    setRepoInfo(null)
    setError(null)
    setFilterText("")
  }, [onClose])

  const isFiltering = filterText.length > 0

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && phase !== "importing") closeAndReset() }}>
      <DialogContent className="sm:max-w-2xl overflow-hidden" style={{ maxWidth: "min(42rem, calc(100vw - 2rem))" }}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-sm">
            <Github className="h-4 w-4" />
            Import from GitHub
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {/* URL input */}
          <div className="flex gap-2">
            <Input
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (phase === "idle" || phase === "list")) void handleFetch() }}
              placeholder="github.com/owner/repo or owner/repo"
              className="h-8 text-xs"
              disabled={phase === "loading" || phase === "importing"}
            />
            {phase === "loading" ? (
              <Button size="sm" variant="outline" className="h-8 shrink-0" disabled>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              </Button>
            ) : (
              <Button size="sm" variant="outline" className="h-8 shrink-0" onClick={handleFetch} disabled={!repoUrl.trim() || phase === "importing"}>
                {phase === "list" ? "Re-fetch" : "Fetch"}
              </Button>
            )}
          </div>

          {error && (
            <p className="text-xs text-destructive flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </p>
          )}

          {/* File list */}
          {phase === "list" && files.length > 0 && (
            <>
              {/* Filter input */}
              <div className="relative">
                <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  placeholder="Filter by path…"
                  className="h-8 text-xs pl-8 pr-8"
                />
                {filterText && (
                  <button
                    onClick={() => setFilterText("")}
                    className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              {/* Status bar */}
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground shrink-0">
                  <span className="font-medium text-foreground">{selectedCount}</span> of {files.length} selected
                  {isFiltering && <> · <span className="font-medium text-foreground">{visibleFiles.length}</span> shown</>}
                </p>
                <div className="flex gap-1 shrink-0">
                  {isFiltering ? (
                    <>
                      <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => toggleVisible(true)}>+shown</Button>
                      <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => toggleVisible(false)}>−shown</Button>
                    </>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => toggleAll(true)}>Select all</Button>
                      <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => toggleAll(false)}>Deselect all</Button>
                    </>
                  )}
                </div>
              </div>

              <ScrollArea className="h-64 rounded-md border">
                <div className="p-1 space-y-0.5">
                  {visibleFiles.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-4">No files match</p>
                  ) : visibleFiles.map((f) => (
                    <div key={f.path} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-accent text-xs min-w-0">
                      <Checkbox
                        id={`gh-${f.path}`}
                        checked={f.selected}
                        onCheckedChange={() => toggleFile(f.path)}
                      />
                      <label htmlFor={`gh-${f.path}`} className="flex-1 truncate cursor-pointer font-mono min-w-0">
                        {f.path}
                      </label>
                      {f.isMdx && (
                        <span className="text-[10px] text-amber-600 dark:text-amber-400 shrink-0">MDX</span>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {mdxCount > 0 && (
                <p className="text-[10px] text-muted-foreground">
                  MDX files will have import/export statements and JSX components stripped.
                </p>
              )}

              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  onClick={handleImport}
                  disabled={selectedCount === 0}
                >
                  Import {selectedCount} file{selectedCount !== 1 ? "s" : ""}
                </Button>
                <Button variant="outline" onClick={closeAndReset}>
                  Cancel
                </Button>
              </div>
            </>
          )}

          {/* Import progress */}
          {phase === "importing" && (
            <div className="space-y-2">
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-200"
                  style={{ width: `${(importProgress.done / importProgress.total) * 100}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground text-center">
                {importProgress.done === importProgress.total
                  ? <><Check className="h-3 w-3 inline mr-1" />Done</>
                  : `Importing ${importProgress.done} / ${importProgress.total}…`}
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
