# Buckets

Buckets are temporary, isolated document collections with their own vector storage. They let you bring in external documents for focused analysis without mixing them into your permanent knowledge base.

Requires the `buckets` plugin (disabled by default — enable in Settings > Plugins).

## Why Buckets?

Your permanent knowledge base is curated — documents you've decided are worth keeping, organized into source directories, scoped and tagged. But sometimes you need to work with documents temporarily:

- Evaluate a framework by loading its docs and chatting with them
- Investigate an incident by pulling in logs and runbooks
- Compare vendor API docs against your existing architecture
- Load conference notes or tutorial transcripts for a focused session

Buckets keep this temporary content isolated. When you're done, delete the bucket and it's gone — your permanent knowledge base is unchanged.

## Built-in Documentation Bucket

On first startup, MarkdownKB creates a permanent **"MarkdownKB Documentation"** bucket containing its own documentation. You can chat with it to learn the system:

- *"How do I set up a scope with exclude patterns?"*
- *"What's the difference between the doc map and knowledge graph?"*
- *"How does hybrid search work?"*

This bucket has no expiration — it persists until you delete it. If you delete it and want it back, restart the app and it will be recreated.

## How Buckets Work

When you create a bucket:

1. **Source scanning** — markdown files are collected from the paths you specify
2. **Parsing and chunking** — files are split into chunks using the same [chunking pipeline](chunking.md) as the main index
3. **Embedding** — chunks are embedded using the same embedding model
4. **Isolated storage** — embeddings go into a bucket-specific ChromaDB collection, completely separate from the main collection

When you search or chat with a bucket selected, retrieval is scoped to that bucket's collection. Your permanent knowledge base is not searched, and the bucket's content doesn't appear in unscoped searches.

Files assigned to a bucket are excluded from the **Files tab** — they appear in the Buckets tab instead, keeping the two views from overlapping.

## The Buckets Tab

The **Buckets tab** is the primary UI for managing buckets. It has a left sidebar listing all buckets and a main panel for detail and creation.

**Sidebar:** Lists all buckets with a color indicator and file count. Expired buckets are dimmed and badged. Clicking a bucket opens its detail view. The **New Bucket** button at the top of the sidebar opens the creation form.

**Detail panel:** Shows the selected bucket's name, stats (file count, chunk count, created time, expiration), sources, and a file table. Action icons in the header:
- **Edit** (pencil) — opens an inline form to change the name, description, expiration, and color
- **Reindex** (refresh) — re-scans the original sources and indexes any new files
- **Export** (download) — downloads the bucket as a portable zip archive
- **Promote** (folder-input) — adds the bucket's source paths to the main watched directories
- **Delete** (trash) — removes the bucket and all its vector data

**Sidebar header:** The **New Bucket** button creates a fresh bucket. The **Import** button (upload icon) restores a bucket from a previously exported zip file.

**Files table:** Lists all files indexed in the bucket with their chunk counts. Click a file to open it in the viewer.

## Creating a Bucket

### From the UI

1. Go to the **Buckets tab**
2. Click **New Bucket** in the left sidebar
3. Enter a name, optional description, source path, glob pattern, expiration, and optional color
4. Click **Create**

### From the API

```json
POST /api/v1/buckets
{
  "name": "grpc-evaluation",
  "sources": [
    {"path": "/home/user/research/grpc-docs", "glob": "**/*.md"}
  ],
  "expires_in": 86400,
  "color": "#6366f1"
}
```

Sources accept absolute paths to files or directories. The `glob` pattern defaults to `**/*.md`. Set `expires_in` to auto-expire the bucket after that many seconds (minimum 60), or omit it for a permanent bucket. `color` accepts any hex color — if omitted, one is auto-assigned from the built-in palette.

**Docker:** If a source path isn't mounted into the container, MarkdownKB automatically adds it to `config/compose.override.yml` and returns `docker_restart_required: true`. Restart with `make docker-down && make docker-up` — the bucket will index on next startup. When a bucket is deleted, its mount is removed from `compose.override.yml` if no other bucket needs it.

**Base path (Docker shortcut):** Set a base path in **Settings → Buckets → Base path** (e.g. `/home/user/buckets`). MarkdownKB mounts that directory once. Every bucket you create under it is accessible immediately — no Docker restart per bucket. The create form pre-fills the path field with `{base_path}/` so you only type the folder name. The first time you set the base path, a single restart is still required to mount the directory.

Buckets are mounted more precisely than watched source directories. A watched source mounts an entire directory tree; a bucket mount covers only the specific path the bucket needs. This means that if you're using buckets for content you're less certain about — third-party docs, external references — Docker's mount boundary limits what any operation can reach to just that bucket's path. See [Write tool security](../reference/mcp-server.md#write-tool-security) for the full picture of what's bounded and what isn't.

## Editing a Bucket

Click the **pencil icon** in the bucket detail panel to enter edit mode. You can change:

- **Name** — rename the bucket
- **Expiration** — set or remove the expiration
- **Color** — pick from the built-in palette

Changes take effect immediately.

Via the API:
```json
PATCH /api/v1/buckets/{id}
{
  "name": "new-name",
  "expires_in": 604800,
  "color": "#ec4899"
}
```

Any combination of fields can be sent — only the fields present in the request are updated.

## Expiration

Buckets can be permanent (no `expires_in`) or set to expire:

- **Permanent** — stays until you explicitly delete it. The built-in docs bucket is permanent.
- **Expiring** — when the expiry time passes, the bucket is flagged as **expired**. It is **not automatically deleted** — it remains visible in the Buckets tab with an "expired" badge until you delete it manually.

Once expired, a bucket is inert:
- It no longer appears in the bucket selector in Chat, Search, Planner, or Doc Map — it cannot be searched or chatted with
- Reindex is blocked
- The detail panel still shows its files so you can review content before deleting

To recover an expired bucket, edit it and set a new expiration (or remove it to make it permanent). This clears the expired flag and restores full access.

To permanently remove it, click the **trash icon** in the bucket detail panel header, or delete it from **Settings > Buckets**.

**Settings > Buckets** shows a sortable table of all buckets with their status (Active, Expiring soon, Expired). You can delete any bucket from this table. Bucket creation is on the Buckets tab — the Settings panel is management-only.

## Bucket Colors

Each bucket gets a color — auto-assigned from the palette on creation, or set explicitly. Colors appear in:

- The **Buckets tab sidebar** — colored dot next to each bucket name
- The **Doc Map** — bucket nodes use the bucket's color instead of a hardcoded red, making it easy to see which external documents belong to which bucket when multiple buckets are selected

The default palette cycles through indigo, violet, pink, orange, teal, cyan, lime, and amber.

## Chat with a Bucket

The bucket detail panel has a **Chat** button that opens a streaming chat drawer scoped entirely to that bucket's content. You don't need to leave the Buckets tab or configure anything — just click and start asking questions.

This is where buckets become qualitatively different from chatting with a single document.

**Single-source chat (what YouTube already does):** When you chat with one video or one article, the LLM only has that one thing to reason from. YouTube itself offers this now. You're not getting more than the source gives you.

**Multi-source synthesis (what bucket chat does):** When you've clipped 5 YouTube videos into a bucket, the chat draws on all 5 simultaneously. The LLM can synthesize, compare, find agreement, surface contradictions, and answer questions that no single video answers. It can also combine clipped videos with uploaded PDFs, articles, and any other content in the bucket — all treated as one coherent collection.

Concrete examples:

- Clip 5 conference talks on a topic. Ask: "What is the consensus view across all these speakers? Where do they disagree?"
- Clip 3 tutorials on the same framework. Ask: "What do all three authors consider essential? What did each one cover that the others missed?"
- Clip a vendor's overview video, their API docs page, and two comparison articles. Ask: "What are the real tradeoffs based on everything here?"
- Build a research bucket with 10 articles. Ask: "What gaps in this field do these authors collectively identify?"

The chat session is ephemeral — it doesn't persist between drawer opens. It's designed for the active working session: open, investigate, close. If you want to save a useful exchange, use the download button in the drawer header to export the transcript.

**File scoping:** Below the drawer header, a row shows how many files are active ("All 12 files" or "3 of 12 files"). Click it to expand a checklist and select exactly which files the chat draws from. Deselecting files narrows retrieval — useful when one video dominates results and you want the LLM to focus on the others.

## Using a Bucket (Search, Planner, Doc Map)

Select a bucket from the sidebar dropdown in Chat, Search, Planner, or Doc Map to scope those features to the bucket's content.

### Bucket Only

When a bucket is active with no scope selected, retrieval is limited to the bucket's documents. This is for focused work — understanding new material in isolation before mixing it with your existing knowledge.

### Bucket + Scope (Combined)

When both a bucket and a scope are active, results come from **both** — your permanent knowledge base (filtered by the scope) and the bucket's documents. Results are tagged by source so you can tell which answers come from your docs and which come from the bucket.

This is the most powerful mode. Use cases:

**Vendor evaluation.** Load vendor API docs into a bucket. Select your "Architecture" scope. Chat: "How does this vendor's authentication approach compare to what we already do?" The LLM has context from both — the vendor's docs and your architecture patterns — and can compare them directly.

**Research synthesis.** Load research papers or conference notes into a bucket. Select your "Research" scope. Search: "What in these new papers overlaps with my existing work?" Results come from both collections, ranked by relevance.

**Migration planning.** Load the new framework's documentation into a bucket. Select the scope covering your current implementation. Planner: "Plan a migration from our current auth system to the new one." The planner has context from both the destination (bucket) and the origin (scope).

**Doc Map overlap discovery.** Select a scope and a bucket in the Doc Map tab. Your permanent documents appear in their usual cluster colors. Bucket documents appear in the bucket's assigned color. Edges between them show where the external material connects to your existing knowledge.

## Adding Documents

There are two ways to add content to a bucket. They can be mixed freely — a bucket can have both a local source path and imported documents.

### From a filesystem path (local sources)

Set a **source path** when creating the bucket. MarkdownKB scans the path for markdown files matching the glob pattern, embeds them, and indexes them into the bucket's collection. The source path is recorded and you can **Reindex** later to pick up new files. In Docker, paths outside the container require a volume mount — see [Docker deployment](../how-to/docker-deployment.md).

Use this when the documents live on disk and you want the bucket to reflect the current state of that directory.

### Via upload or URL clip (no local path needed)

From the bucket detail panel, you can import content directly without any filesystem path:

- **URL clip** — paste a URL (article, YouTube video, documentation page) into the import field and click **Clip**. The converter plugin fetches and converts the page to markdown, then stores it in the bucket. Requires the `converter` plugin.
- **File upload** — drag files into the drop zone or click to browse. Supported formats include PDF, Word, PowerPoint, Excel, EPUB, HTML, and more. Each file is converted to markdown and stored in the bucket. Requires the `converter` plugin.

Uploaded and clipped documents are stored as **virtual documents** — they exist only as vectors in ChromaDB with paths like `bucket://bucket-name/filename.md`. There is no file on disk. They are permanent members of the bucket and survive reindexes. They do not require a source path or Docker mount.

Use this when you want to quickly load external content without managing files on disk — articles you've found, PDFs sent to you, pages you want to reference in a session.

### Via the API (content push)

The API supports pushing markdown content directly, without any files on disk:

```json
POST /api/v1/buckets/{id}/documents
{
  "documents": [
    {"name": "api-reference.md", "content": "# API Reference\n\n..."}
  ]
}
```

Pushed documents work identically to UI uploads — virtual paths, no filesystem. Designed for remote agents and integrations. Also available via the `bucket_push` MCP tool.

### Renaming virtual documents

Virtual documents (uploaded files, URL clips, pushed content) can be renamed from the bucket files table — click the pencil icon on any row with a `bucket://` path. The name is slugified automatically, so pasting a full title like `Karpathy's Wiki vs. Open Brain.` produces `karpathys-wiki-vs-open-brain.md`.

Filesystem-sourced files cannot be renamed this way — rename them on disk and reindex to update the bucket.

Via the API:
```json
PATCH /api/v1/buckets/{id}/documents
{
  "old_path": "bucket://my-bucket/old-name.md",
  "new_name": "new-name"
}
```

### Adding more filesystem sources

To add another source path to an existing bucket without recreating it:

```json
POST /api/v1/buckets/{id}/add
{
  "sources": [{"path": "/home/user/more-docs", "glob": "**/*.md"}]
}
```

Duplicate files (same path) are skipped.

### Reading files back

You can read the full content of any bucket file (filesystem-sourced or pushed) via `GET /api/v1/buckets/{id}/file?path=...` or the `bucket_read_file` MCP tool. Content is reconstructed from stored chunks.

## MCP Tools

When the buckets plugin is enabled, agents can create, search, and chat with buckets via MCP:

| Tool | Description |
|------|-------------|
| `bucket_create` | Create a bucket from source paths |
| `bucket_add` | Add documents to an existing bucket |
| `bucket_push` | Push documents by content (no filesystem needed) |
| `bucket_list` | List all buckets |
| `bucket_list_files` | List files in a bucket |
| `bucket_read_file` | Read full content of a bucket file |
| `bucket_search` | Search within a bucket |
| `bucket_chat` | RAG chat scoped to a bucket |
| `bucket_delete` | Delete a bucket |

Write tools (create, add, delete) respect the `mcp.read_only` flag, with an override via `mcp.allow_bucket_writes` — this allows bucket operations while keeping the main knowledge base read-only, since buckets are ephemeral and isolated.

## Configuration

```yaml
plugins:
  buckets:
    enabled: true
```

## Storage

Each bucket gets its own ChromaDB collection (`bucket_{id}`), stored alongside the main collection. Bucket metadata (name, description, sources, expiration, color) is in `{data_directory}/buckets.db`. File membership records (which files belong to which bucket) are also stored there, used to exclude bucket files from the Files tab. Deleting a bucket removes the DB record, the file memberships, and the ChromaDB collection.
