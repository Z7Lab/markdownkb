import { useEffect, useState, memo } from "react"
import { Check, Copy } from "lucide-react"
import { cn } from "@/lib/utils"

// Lazy-load shiki to avoid blocking initial render
let highlighterPromise: Promise<import("shiki").HighlighterGeneric<any, any>> | null = null

function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then((mod) =>
      mod.createHighlighter({
        themes: ["github-dark", "github-light"],
        langs: [
          "javascript", "typescript", "python", "bash", "sh", "shell",
          "json", "yaml", "html", "css", "sql", "markdown", "md",
          "rust", "go", "java", "c", "cpp", "ruby", "php",
          "dockerfile", "toml", "xml", "diff", "plaintext",
        ],
      }),
    )
  }
  return highlighterPromise
}

export const CodeBlock = memo(function CodeBlock({
  code,
  language,
  className,
}: {
  code: string
  language?: string
  className?: string
}) {
  const [html, setHtml] = useState("")
  const [copied, setCopied] = useState(false)

  const lang = (language || "plaintext").toLowerCase().replace(/^language-/, "")
  const displayLang = lang === "plaintext" ? "" : lang

  useEffect(() => {
    let cancelled = false
    getHighlighter()
      .then((hl) => {
        if (cancelled) return
        try {
          const result = hl.codeToHtml(code, {
            lang: hl.getLoadedLanguages().includes(lang) ? lang : "plaintext",
            themes: { dark: "github-dark", light: "github-light" },
          })
          setHtml(result)
        } catch {
          // Fallback — no highlighting
          setHtml("")
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [code, lang])

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className={cn("group relative rounded-lg overflow-hidden my-3", className)}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-zinc-800 dark:bg-zinc-900 text-zinc-400 text-xs">
        <span className="font-mono">{displayLang}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-zinc-200 transition-colors"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {/* Code body */}
      {html ? (
        <div
          className="overflow-x-auto text-sm [&_pre]:!m-0 [&_pre]:!rounded-none [&_pre]:!p-4 [&_code]:!text-sm"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="overflow-x-auto bg-zinc-900 dark:bg-zinc-950 text-zinc-100 p-4 m-0 text-sm">
          <code className="font-mono">{code}</code>
        </pre>
      )}
    </div>
  )
})
