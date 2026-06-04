# Importing Content

The **Import** tab is the one place to add new content to your knowledge base. It appears in the sidebar when the `converter` plugin is enabled and offers four ingestion methods plus a destination picker. The same panel is reused inside the **Buckets** tab (pre-wired to the active bucket).

> The Import tab only shows the methods that are actually available right now — it asks the backend (`GET /api/v1/import/capabilities`) what's enabled and renders accordingly. If a method is missing, the prerequisite below isn't met.

## Pick a destination

At the top of the tab, choose where imported content lands:

- **Source directories** — any **writable** source (set in Settings → Sources). Read-only sources and project-root mounts are not offered (they can't receive writes).
- **Buckets** — if the `buckets` plugin is enabled, each bucket appears as a destination. Bucket documents are stored as virtual entries (`bucket://…`), not files on disk.

In the Buckets tab, the destination is always the bucket you're viewing.

## The four methods

### 1. Upload a file

Drag files onto the drop zone or click to browse. The **Supported types** box shows which formats are ready (green) vs. need enabling (grey) — click **Configure** to jump to Settings → File Converter. Conversion runs as a background job with a progress bar; the converted markdown is written to the destination and indexed automatically.

- `.md` files are accepted and stored as-is (no conversion).
- **PDF, DOCX, PPTX, XLSX, and audio require the `full` Docker image.** See [Docker Deployment → Image variants](docker-deployment.md#image-variants).
- Each format's sub-converter (web, office, pdf, misc, audio) can be toggled independently in Settings → File Converter.

### 2. Clip from the web

Paste a URL (article, docs page, or YouTube video) and click **Clip**. The page is fetched, converted to markdown, and ingested. YouTube transcript extraction requires the `full` image; without it, only page metadata is captured. URL fetching is SSRF-guarded.

### 3. Audio transcription

Drop an audio file (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.webm`) into the upload zone. A status line under the drop zone shows whether transcription is ready. Configure the provider in Settings → File Converter:

- **Local** (`faster-whisper`) — download a model (tiny → large-v3) in settings first. Local transcription needs the `full` image and shows per-segment progress.
- **Remote** — point at an OpenAI-compatible `/v1/audio/transcriptions` API base. Use the **Test connection** button to verify reachability.

### 4. Create a markdown note

Click **New note** (top-right of the Import tab header, or in the Buckets "Add content" row) to open an editor: type a filename and markdown content. Spaces in the filename become hyphens and `.md` is appended automatically; a live preview shows the resolved filename.

This method appears only when the `write_api` plugin **and** the `save_document` MCP flag are both enabled.

## Prerequisites at a glance

| To use… | You need… |
|---------|-----------|
| Any import method | `converter` plugin enabled; at least one writable destination |
| PDF / DOCX / PPTX / XLSX | `full` Docker image + that sub-converter enabled |
| Audio (local) | `full` image + a downloaded Whisper model |
| Audio (remote) | An OpenAI-compatible transcription API base URL |
| YouTube transcripts | `full` image |
| Create a note | `write_api` plugin + `save_document` MCP flag |
| Bucket destinations | `buckets` plugin enabled |

## See also

- [UI Tabs and Plugins](../reference/ui-tabs-and-plugins.md) — the Import tab and the plugins that power it
- [Docker Deployment](docker-deployment.md) — base vs. `full` image variants
- [Buckets](../explanation/buckets.md) — scoped collections that reuse the same ingestion panel
- [Writing Documents](writing-documents.md) — programmatic writes via REST/MCP
