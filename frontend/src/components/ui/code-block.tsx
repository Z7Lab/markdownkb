import { useState, memo } from "react"
import { Check, Copy } from "lucide-react"
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"
import { useIsDark } from "@/hooks/use-is-dark"
import { cn } from "@/lib/utils"

// Register only the languages we need to keep bundle size small
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript"
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript"
import python from "react-syntax-highlighter/dist/esm/languages/prism/python"
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash"
import json from "react-syntax-highlighter/dist/esm/languages/prism/json"
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml"
import markup from "react-syntax-highlighter/dist/esm/languages/prism/markup"
import css from "react-syntax-highlighter/dist/esm/languages/prism/css"
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql"
import rust from "react-syntax-highlighter/dist/esm/languages/prism/rust"
import go from "react-syntax-highlighter/dist/esm/languages/prism/go"
import java from "react-syntax-highlighter/dist/esm/languages/prism/java"
import c from "react-syntax-highlighter/dist/esm/languages/prism/c"
import cpp from "react-syntax-highlighter/dist/esm/languages/prism/cpp"
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown"
import docker from "react-syntax-highlighter/dist/esm/languages/prism/docker"
import diff from "react-syntax-highlighter/dist/esm/languages/prism/diff"
import toml from "react-syntax-highlighter/dist/esm/languages/prism/toml"

SyntaxHighlighter.registerLanguage("javascript", javascript)
SyntaxHighlighter.registerLanguage("jsx", javascript)
SyntaxHighlighter.registerLanguage("typescript", typescript)
SyntaxHighlighter.registerLanguage("tsx", typescript)
SyntaxHighlighter.registerLanguage("python", python)
SyntaxHighlighter.registerLanguage("bash", bash)
SyntaxHighlighter.registerLanguage("sh", bash)
SyntaxHighlighter.registerLanguage("shell", bash)
SyntaxHighlighter.registerLanguage("json", json)
SyntaxHighlighter.registerLanguage("yaml", yaml)
SyntaxHighlighter.registerLanguage("yml", yaml)
SyntaxHighlighter.registerLanguage("html", markup)
SyntaxHighlighter.registerLanguage("xml", markup)
SyntaxHighlighter.registerLanguage("css", css)
SyntaxHighlighter.registerLanguage("sql", sql)
SyntaxHighlighter.registerLanguage("rust", rust)
SyntaxHighlighter.registerLanguage("go", go)
SyntaxHighlighter.registerLanguage("java", java)
SyntaxHighlighter.registerLanguage("c", c)
SyntaxHighlighter.registerLanguage("cpp", cpp)
SyntaxHighlighter.registerLanguage("markdown", markdown)
SyntaxHighlighter.registerLanguage("md", markdown)
SyntaxHighlighter.registerLanguage("dockerfile", docker)
SyntaxHighlighter.registerLanguage("diff", diff)
SyntaxHighlighter.registerLanguage("toml", toml)

export const CodeBlock = memo(function CodeBlock({
  code,
  language,
  className,
}: {
  code: string
  language?: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const isDark = useIsDark()

  const lang = (language || "").toLowerCase().replace(/^language-/, "")
  const displayLang = lang || ""

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className={cn("group relative rounded-lg overflow-hidden my-3 max-w-full", className)}>
      {/* Header bar */}
      <div className={cn(
        "flex items-center justify-between px-4 py-1.5 text-xs",
        isDark ? "bg-zinc-700 text-zinc-400" : "bg-zinc-200 text-zinc-600",
      )}>
        <span className="font-mono">{displayLang}</span>
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1 transition-colors",
            isDark ? "hover:text-zinc-200" : "hover:text-zinc-900",
          )}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {/* Code body — synchronous, no flicker */}
      <SyntaxHighlighter
        language={lang || "plaintext"}
        style={isDark ? oneDark : oneLight}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "0.875rem",
          padding: "1rem",
          overflowX: "auto",
        }}
        codeTagProps={{ style: { fontSize: "0.875rem" } }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
})
