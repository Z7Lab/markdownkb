# Chat

The Chat tab is the primary interface for asking questions about your knowledge base. You type a question, the system retrieves relevant document chunks, and the LLM generates an answer grounded in your actual documents — with source citations so you can verify.

This is a core feature, always available (not a plugin).

## How It Works

When you send a message:

1. **Query enhancement** — if intelligent search is enabled, the LLM extracts keywords and expands acronyms before retrieval
2. **Retrieval** — your message is matched against all indexed chunks using [hybrid search](retrieval.md) (vector similarity + BM25 keywords), filtered by active scopes, tags, and exclude patterns
3. **Context building** — the top matching chunks are formatted into a prompt with source attribution
4. **LLM response** — the prompt (system instructions + retrieved context + conversation history + your message) is sent to the configured LLM
5. **Streaming** — the response streams token-by-token to the UI in real-time
6. **Source tracking** — source documents referenced in the response are saved with the message

## Conversation Threads

Every chat creates a **thread** — a named conversation with full message history. Threads appear in the sidebar and persist across sessions.

- **New Chat** starts a fresh thread (the title is auto-generated from your first message)
- **Switching threads** loads the full conversation history
- **Rename** a thread by double-clicking its title in the sidebar or using the pencil icon
- **Delete** removes the thread and all its messages

### Conversation Context

The LLM sees your conversation history when responding, so follow-up questions work naturally:

```
You: How does the file watcher work?
AI:  The file watcher uses watchdog to detect changes...

You: What about rename events?
AI:  When a file is renamed, the watcher checks if...
```

The LLM knows "What about rename events?" refers to the file watcher because it has the conversation context.

## Controls

Three controls appear below the message area:

### Clear

Resets the current conversation — removes all messages from the UI and clears the thread's history. The thread still exists in the sidebar but starts fresh.

### Continue

Sends "Continue your previous response from where you left off." Useful when the LLM's response was cut short by the `max_tokens` limit. The LLM picks up where it stopped because it has the conversation history.

### Save MD / Save HTML

Downloads the current conversation as a file. **Save MD** downloads a plain markdown transcript. **Save HTML** downloads a self-contained HTML file with rendered markdown formatting — useful for sharing or archiving a formatted version that can be opened in any browser without tooling.

## Scoped Chat

When you select a scope or markdown tags in the sidebar, retrieval is filtered to only those documents. This lets you have focused conversations:

- Select the "Infrastructure Docs" scope → chat only retrieves from infrastructure documentation
- Check the "architecture" tag → chat only retrieves from documents tagged with architecture
- Combine both → chat retrieves from infrastructure docs OR architecture-tagged docs

Scope and tag selections persist across tab switches (stored in localStorage), so switching from Chat to Search and back keeps your filter active.

## Bucket Chat

When the buckets plugin is enabled and a bucket is selected in the sidebar:

- **Bucket only** (no scope selected) — chat retrieves from the bucket's documents only. Good for focused conversations about the bucket's content.
- **Bucket + scope** — chat retrieves from both the bucket AND your permanent knowledge base (filtered by the scope). Results are merged and the LLM has context from both. This is the most powerful mode — ask questions that compare or synthesize across both document sets. For example: "How does this vendor's auth approach compare to what we already do?"

You can also chat with a bucket directly from the **Buckets tab** — the bucket detail panel has a Chat button that opens a streaming drawer scoped to that bucket. This is faster for the common case of "I just loaded some content, let me ask it questions." The drawer chat is ephemeral (no thread persistence) and designed for active investigation sessions.

The key advantage of bucket chat over chatting with a single source: **synthesis across all content simultaneously**. A bucket with 5 YouTube transcripts, 3 PDFs, and 4 articles answers questions by drawing on all of them at once. You can ask what the collective material agrees on, where it conflicts, and what questions it leaves unanswered — answers that no single source could give you.

See [Buckets](buckets.md#chat-with-a-bucket) for detailed use cases.

## Model Picker

The sidebar includes a model picker dropdown showing the currently active LLM. This is read-only — it shows what's configured in Settings > Chat Model. To switch models, go to Settings.

## Source Citations

When the LLM references specific documents in its response, the source files are tracked and displayed. Click a source to open the file viewer and see the full document.

Sources are saved per-message, so when you reload a thread, the citations are preserved.

## Diagnostics Mode

When `core.diagnostics` is enabled in settings, chat messages show additional metadata — retrieval scores, chunk details, and timing information. This is a development/debugging feature, not intended for normal use.

## Configuration

Chat behavior is controlled by generation and retrieval settings. Generation parameters are **per-provider** — each provider (Ollama, Venice, etc.) stores its own temperature, max_tokens, and num_ctx. Switching providers in Settings shows that provider's saved values.

### Generation Parameters

| Setting | Default | Description |
|---------|---------|-------------|
| `temperature` | 0.3 | Response randomness. Lower = more focused and deterministic. Higher = more creative. |
| `max_tokens` | 2048 | Maximum tokens in the LLM response (output limit). |
| `num_ctx` | model default | **Ollama only.** Total context window (input + output). More context = more RAM. |

**How max_tokens and num_ctx relate (Ollama):** `num_ctx` is the total context window — your documents, conversation history, AND the response all must fit within it. `max_tokens` limits just the response portion. If `num_ctx` is 4096 and your input uses 3000 tokens, the response is capped at ~1096 tokens regardless of the `max_tokens` setting. Set `num_ctx` higher (8192, 32768) if you need longer responses or more document context.

**Cloud providers (Anthropic, Venice, OpenAI):** Only `max_tokens` applies. Context window is managed by the provider.

**Local servers (llama.cpp, LM Studio):** Context window is configured on the server (`-c` flag for llama.cpp). `max_tokens` limits the response.

### Retrieval Parameters

```yaml
retrieval:
  top_k: 10               # Chunks retrieved per query
  score_threshold: 0.25   # Minimum relevance score
  hybrid_search: true      # Use BM25 + vector fusion
  bm25_weight: 0.5        # Keyword vs semantic balance
```

The system prompt that instructs the LLM how to respond can be customized in Settings > Prompts.

## How It Differs from Search

- **Chat** is conversational — ask follow-up questions, the LLM has context from the conversation
- **Search** is query-response — enter a query, get ranked results, optionally generate a one-off summary

Use chat when you want to explore a topic interactively. Use search when you want to see what documents exist on a topic and where the information lives.
