import { useMemo, useState } from "react"
import { cn, basename, dirname } from "@/lib/utils"
import { AppSidebar } from "@/components/ui/app-sidebar"
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
} from "lucide-react"
import type { TrackedFile } from "@/lib/types"

interface FolderNode {
  name: string
  fullPath: string
  fileCount: number
  children: FolderNode[]
}

function sortTree(nodes: FolderNode[]) {
  nodes.sort((a, b) => a.name.localeCompare(b.name))
  for (const n of nodes) sortTree(n.children)
}

function buildFolderTree(files: TrackedFile[]): FolderNode[] {
  const rootMap = new Map<string, FolderNode>()

  for (const file of files) {
    const sr = file.source_root.replace(/\/$/, "")
    if (!rootMap.has(sr)) {
      rootMap.set(sr, { name: basename(sr), fullPath: sr, fileCount: 0, children: [] })
    }
    const root = rootMap.get(sr)!
    const fileDir = dirname(file.path)

    if (fileDir === sr) {
      root.fileCount++
      continue
    }

    const relative = fileDir.slice(sr.length).replace(/^\//, "")
    const segments = relative.split("/").filter(Boolean)

    let current = root
    let builtPath = sr
    for (const seg of segments) {
      builtPath += "/" + seg
      let child = current.children.find((c) => c.name === seg)
      if (!child) {
        child = { name: seg, fullPath: builtPath, fileCount: 0, children: [] }
        current.children.push(child)
      }
      current = child
    }
    current.fileCount++
  }

  const roots = Array.from(rootMap.values())
  sortTree(roots)
  return roots
}

function FolderTreeNode({
  node,
  depth,
  selectedFolder,
  onSelectFolder,
  expandedPaths,
  toggleExpand,
}: {
  node: FolderNode
  depth: number
  selectedFolder: string | null
  onSelectFolder: (path: string | null) => void
  expandedPaths: Set<string>
  toggleExpand: (path: string) => void
}) {
  const isExpanded = expandedPaths.has(node.fullPath)
  const isSelected = selectedFolder === node.fullPath
  const hasChildren = node.children.length > 0

  return (
    <>
      <button
        type="button"
        className={cn(
          "w-full text-left rounded-md py-1 text-sm flex items-center gap-1 hover:bg-accent",
          isSelected && "bg-accent font-medium",
        )}
        style={{ paddingLeft: `${8 + depth * 16}px`, paddingRight: 8 }}
        onClick={() => {
          onSelectFolder(node.fullPath)
          if (hasChildren) toggleExpand(node.fullPath)
        }}
      >
        {hasChildren ? (
          isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        {isExpanded && hasChildren ? (
          <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <span className="truncate">{node.name}</span>
        {node.fileCount > 0 && (
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {node.fileCount}
          </span>
        )}
      </button>
      {isExpanded &&
        node.children.map((child) => (
          <FolderTreeNode
            key={child.fullPath}
            node={child}
            depth={depth + 1}
            selectedFolder={selectedFolder}
            onSelectFolder={onSelectFolder}
            expandedPaths={expandedPaths}
            toggleExpand={toggleExpand}
          />
        ))}
    </>
  )
}

export function FolderTree({
  files,
  selectedFolder,
  onSelectFolder,
}: {
  files: TrackedFile[]
  selectedFolder: string | null
  onSelectFolder: (path: string | null) => void
}) {
  const roots = useMemo(() => buildFolderTree(files), [files])

  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    // Initialize with root paths from the memoized roots (avoid double computation)
    return new Set(roots.map((r) => r.fullPath))
  })

  const toggleExpand = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  return (
    <AppSidebar
      header={<h3 className="text-sm font-semibold text-muted-foreground">Watch Directories</h3>}
    >
      <div className="p-2 space-y-0.5">
        <button
          type="button"
          className={cn(
            "w-full text-left rounded-md px-2 py-1 text-sm flex items-center gap-1.5 hover:bg-accent",
            selectedFolder === null && "bg-accent font-medium",
          )}
          onClick={() => onSelectFolder(null)}
        >
          <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate">All files</span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {files.length}
          </span>
        </button>
        {roots.map((node) => (
          <FolderTreeNode
            key={node.fullPath}
            node={node}
            depth={0}
            selectedFolder={selectedFolder}
            onSelectFolder={onSelectFolder}
            expandedPaths={expandedPaths}
            toggleExpand={toggleExpand}
          />
        ))}
      </div>
    </AppSidebar>
  )
}
