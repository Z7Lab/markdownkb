import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function relativeTime(iso: string): string {
  const normalized = iso.includes("T") ? iso : `${iso.replace(" ", "T")}Z`
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
