/**
 * Remark plugin that transforms [N] citation references into link nodes.
 *
 * Text like "This is important [1] and that too [2]" becomes:
 *   Text("This is important ") + Link(url="#cite-1", "1") + Text(" and that too ") + Link(url="#cite-2", "2")
 *
 * The Markdown component's `components.a` override then renders #cite-N links
 * as clickable superscript citation badges.
 */
import type { Node, Parent } from "unist"
import type { Text, PhrasingContent } from "mdast"
import { visit } from "unist-util-visit"

const CITE_RE = /\[(\d+)\]/g

export function remarkCitations() {
  return (tree: Node) => {
    visit(tree, "text", (node: Text, index: number | undefined, parent: Parent | undefined) => {
      if (index === undefined || !parent) return
      const text: string = node.value
      if (!CITE_RE.test(text)) return

      // Reset regex state
      CITE_RE.lastIndex = 0

      const children: PhrasingContent[] = []
      let lastIndex = 0
      let match: RegExpExecArray | null

      while ((match = CITE_RE.exec(text)) !== null) {
        // Text before the match
        if (match.index > lastIndex) {
          children.push({ type: "text", value: text.slice(lastIndex, match.index) })
        }

        // Citation link node
        children.push({
          type: "link",
          url: `#cite-${match[1]}`,
          title: "citation",
          children: [{ type: "text", value: match[1] }],
        })

        lastIndex = match.index + match[0].length
      }

      // Remaining text after last match
      if (lastIndex < text.length) {
        children.push({ type: "text", value: text.slice(lastIndex) })
      }

      // Replace the original text node with the new children
      if (children.length > 0) {
        parent.children.splice(index, 1, ...children)
        return index + children.length
      }
    })
  }
}
