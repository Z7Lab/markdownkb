import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

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

/**
 * Copy text to clipboard with fallback for non-secure contexts (e.g. LAN access over HTTP).
 * Returns true if the copy succeeded.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
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
    return false
  } finally {
    document.body.removeChild(textarea)
  }
}
