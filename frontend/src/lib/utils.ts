import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { ChatMessage } from "@/lib/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Normalize a server timestamp (SQLite datetime without Z) to a proper UTC ISO string. */
export function utc(ts: string): string {
  return ts.includes("T") ? ts : `${ts.replace(" ", "T")}Z`
}

export function relativeTime(iso: string): string {
  const normalized = utc(iso)
  const ms = Date.now() - new Date(normalized).getTime()
  if (Number.isNaN(ms)) return ""
  const min = Math.floor(ms / 60000)
  if (min < 1) return "just now"
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const d = Math.floor(hr / 24)
  if (d < 30) return `${d}d ago`
  return new Date(normalized).toLocaleDateString()
}

/**
 * Extract the filename from a file path
 */
export function basename(path: string): string {
  return path.split("/").pop() ?? path
}

/**
 * Extract the directory path from a file path
 */
export function dirname(path: string): string {
  const parts = path.split("/")
  parts.pop()
  return parts.join("/") || "/"
}

export interface ParsedFrontmatter {
  tags: string[]
  content: string
}

/**
 * Parse YAML frontmatter from a markdown file's raw content.
 * Supports inline array format (tags: [a, b]) and YAML list format.
 */
export function parseFrontmatter(raw: string): ParsedFrontmatter {
  const frontmatterRegex = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/
  const match = raw.match(frontmatterRegex)

  if (!match) {
    return { tags: [], content: raw }
  }

  const [, frontmatter, content] = match as RegExpMatchArray

  // Try inline array format: tags: [tag1, tag2]
  const inlineMatch = frontmatter!.match(/tags:\s*\[(.*?)\]/)
  if (inlineMatch) {
    const tags = inlineMatch[1]!
      .split(',')
      .map(t => t.trim().replace(/['"]/g, ''))
      .filter(Boolean)
    return { tags, content: content! }
  }

  // Try YAML list format:
  // tags:
  // - tag1
  // - tag2
  const listMatch = frontmatter!.match(/tags:\s*\n((?:\s*-\s*.+\n?)+)/)
  if (listMatch) {
    const tags = listMatch[1]!
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.startsWith('-'))
      .map(line => line.substring(1).trim().replace(/['"]/g, ''))
      .filter(Boolean)
    return { tags, content: content! }
  }

  return { tags: [], content: content! }
}

/**
 * Slugify a string into a safe markdown filename (without the .md extension).
 * Strips punctuation, collapses whitespace to hyphens, lowercases, trims to 80 chars.
 * Example: "Karpathy's Wiki vs. Open Brain." → "karpathys-wiki-vs-open-brain"
 */
export function slugifyFilename(text: string): string {
  return text
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .toLowerCase()
    .slice(0, 80)
    .replace(/-+$/, "")
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

export function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: "text/markdown" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename.endsWith(".md") ? filename : `${filename}.md`
  a.click()
  URL.revokeObjectURL(url)
}

export function formatChatTranscript(title: string, messages: ChatMessage[]): string {
  const date = new Date().toLocaleDateString()
  const lines = [`# ${title} (${date})`, ""]
  for (const msg of messages) {
    if (!msg.content) continue
    lines.push(msg.role === "user" ? `**You:** ${msg.content}` : `**Assistant:** ${msg.content}`)
    lines.push("")
  }
  return lines.join("\n")
}

function _esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
}

function _inlineText(s: string): string {
  s = _esc(s)
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => `<img alt="${_esc(alt)}" src="${src}">`)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, href) => `<a href="${href}">${text}</a>`)
  s = s.replace(/~~(.+?)~~/g, "<del>$1</del>")
  s = s.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  s = s.replace(/__(.+?)__/g, "<strong>$1</strong>")
  s = s.replace(/\*(.+?)\*/g, "<em>$1</em>")
  s = s.replace(/(?<![a-zA-Z0-9_])_(.+?)_(?![a-zA-Z0-9_])/g, "<em>$1</em>")
  return s
}

function _inline(s: string): string {
  const out: string[] = []
  const codeRe = /`([^`]+)`/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = codeRe.exec(s)) !== null) {
    if (m.index > last) out.push(_inlineText(s.slice(last, m.index)))
    out.push(`<code>${_esc(m[1]!)}</code>`)
    last = m.index + m[0].length
  }
  if (last < s.length) out.push(_inlineText(s.slice(last)))
  return out.join("")
}

function mdToHtml(md: string): string {
  const lines = md.split("\n")
  const chunks: string[] = []
  let i = 0
  let listType: "ul" | "ol" | null = null
  const para: string[] = []

  function flushPara() {
    if (!para.length) return
    chunks.push(`<p>${para.map(_inline).join("<br>")}</p>`)
    para.length = 0
  }
  function flushList() {
    if (!listType) return
    chunks.push(`</${listType}>`)
    listType = null
  }

  while (i < lines.length) {
    const line = lines[i]!

    if (/^```/.test(line)) {
      flushPara(); flushList()
      const lang = line.slice(3).trim()
      i++
      const code: string[] = []
      while (i < lines.length && !/^```\s*$/.test(lines[i]!)) { code.push(_esc(lines[i]!)); i++ }
      i++
      chunks.push(`<pre><code${lang ? ` class="language-${_esc(lang)}"` : ""}>${code.join("\n")}</code></pre>`)
      continue
    }

    const hm = line.match(/^(#{1,6}) (.+)$/)
    if (hm) {
      flushPara(); flushList()
      const lv = hm[1]!.length
      chunks.push(`<h${lv}>${_inline(hm[2]!)}</h${lv}>`)
      i++; continue
    }

    if (/^([-*_])\1{2,}\s*$/.test(line)) {
      flushPara(); flushList(); chunks.push("<hr>"); i++; continue
    }

    if (line.startsWith("> ")) {
      flushPara(); flushList()
      chunks.push(`<blockquote><p>${_inline(line.slice(2))}</p></blockquote>`)
      i++; continue
    }

    if (line.startsWith("|") && /^\|[-| :]+\|/.test(lines[i + 1] ?? "")) {
      flushPara(); flushList()
      const headers = line.split("|").slice(1, -1).map(h => h.trim())
      i += 2
      chunks.push("<table><thead><tr>")
      headers.forEach(h => chunks.push(`<th>${_inline(h)}</th>`))
      chunks.push("</tr></thead><tbody>")
      while (i < lines.length && lines[i]!.startsWith("|")) {
        const cells = lines[i]!.split("|").slice(1, -1).map(c => c.trim())
        chunks.push("<tr>")
        cells.forEach(c => chunks.push(`<td>${_inline(c)}</td>`))
        chunks.push("</tr>")
        i++
      }
      chunks.push("</tbody></table>")
      continue
    }

    const ulm = line.match(/^(\s*)[-*+] (\[[ x]\] )?(.+)$/)
    if (ulm) {
      flushPara()
      if (listType !== "ul") { if (listType) chunks.push(`</${listType}>`); chunks.push("<ul>"); listType = "ul" }
      const checked = ulm[2] === "[x] "
      const cb = ulm[2] ? `<input type="checkbox" disabled${checked ? " checked" : ""}> ` : ""
      chunks.push(`<li>${cb}${_inline(ulm[3]!)}</li>`)
      i++; continue
    }

    const olm = line.match(/^\d+\. (.+)$/)
    if (olm) {
      flushPara()
      if (listType !== "ol") { if (listType) chunks.push(`</${listType}>`); chunks.push("<ol>"); listType = "ol" }
      chunks.push(`<li>${_inline(olm[1]!)}</li>`)
      i++; continue
    }

    if (!line.trim()) { flushPara(); flushList(); i++; continue }

    flushList()
    para.push(line)
    i++
  }
  flushPara(); flushList()
  return chunks.join("\n")
}

export function downloadHtml(content: string, filename: string): void {
  const body = mdToHtml(content)
  const title = _esc(filename.replace(/\.[^.]+$/, ""))
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:16px;line-height:1.6;color:#24292f;max-width:800px;margin:40px auto;padding:0 16px}
h1,h2,h3,h4,h5,h6{font-weight:600;line-height:1.25;margin-top:24px;margin-bottom:16px}
h1,h2{border-bottom:1px solid #d1d9e0;padding-bottom:.3em}
h1{font-size:2em}h2{font-size:1.5em}h3{font-size:1.25em}
p{margin-top:0;margin-bottom:16px}
code{font-family:"SFMono-Regular",Consolas,monospace;font-size:85%;background:#f6f8fa;padding:.2em .4em;border-radius:6px}
pre{background:#f6f8fa;border-radius:6px;padding:16px;overflow:auto;margin-bottom:16px}
pre code{background:none;padding:0;font-size:100%}
blockquote{border-left:.25em solid #d1d9e0;color:#57606a;margin:0 0 16px;padding:0 1em}
blockquote p{margin-bottom:0}
ul,ol{padding-left:2em;margin-top:0;margin-bottom:16px}
li{margin-top:.25em}
table{border-collapse:collapse;width:100%;margin-bottom:16px}
th,td{border:1px solid #d1d9e0;padding:6px 13px}
th{background:#f6f8fa;font-weight:600}
tr:nth-child(even){background:#f6f8fa}
hr{border:none;border-top:1px solid #d1d9e0;margin:24px 0}
img{max-width:100%}
a{color:#0969da;text-decoration:none}
a:hover{text-decoration:underline}
del{color:#57606a}
input[type=checkbox]{margin-right:.5em}
</style>
</head>
<body>
${body}
</body>
</html>`
  const blob = new Blob([html], { type: "text/html" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename.endsWith(".html") ? filename : `${filename}.html`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Copy text to clipboard with fallback for non-secure contexts (e.g. LAN access over HTTP).
 * Returns true if the copy succeeded.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall through to legacy method
    }
  }
  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.style.position = "fixed"
  textarea.style.opacity = "0"
  document.body.appendChild(textarea)
  textarea.select()
  try {
    return document.execCommand("copy")
  } catch {
    return false // execCommand throws in some sandboxed contexts; report failure
  } finally {
    document.body.removeChild(textarea)
  }
}
