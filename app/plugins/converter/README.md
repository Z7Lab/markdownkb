# File Converter Plugin

Batch convert documents (DOCX, PDF, HTML, RST, TXT, EPUB, ODT, RTF, CSV) to markdown using Pandoc. Converted files are saved to a watched source directory where MarkdownKB auto-indexes them.

**Feature flag:** `converter`
**Prefix:** `/api/converter`

## Prerequisites

This plugin requires **Pandoc** to be installed on the system. MarkdownKB does not bundle Pandoc — it's a system dependency you install separately.

### Native install

```bash
# Debian/Ubuntu
apt install pandoc

# macOS
brew install pandoc
```

### Docker

The base MarkdownKB Docker image does not include Pandoc. Extend the image:

```dockerfile
FROM markdownkb:latest
USER root
RUN apt-get update && apt-get install -y --no-install-recommends pandoc poppler-utils \
    && rm -rf /var/lib/apt/lists/*
USER markdownkb
```

Build and use this image instead:

```bash
docker build -t markdownkb-full -f Dockerfile.full .
```

### Optional: PDF support

For better PDF text extraction, install `poppler-utils` (provides `pdftotext`). Without it, the plugin falls back to Pandoc's PDF handling which is less reliable.

```bash
apt install poppler-utils
```

## Supported Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| Microsoft Word | `.docx` | Google Docs Takeout exports as DOCX |
| PDF | `.pdf` | Uses pdftotext if available, falls back to Pandoc |
| HTML | `.html`, `.htm` | Web pages, saved articles |
| reStructuredText | `.rst` | Python documentation format |
| Plain Text | `.txt` | Wrapped as-is in markdown |
| EPUB | `.epub` | E-books |
| LibreOffice | `.odt` | Open Document format |
| Rich Text | `.rtf` | Legacy format |
| CSV | `.csv` | Converted to markdown tables |

## Use Cases

- **Google Docs migration.** Export via Google Takeout (downloads as .docx), point the converter at the export directory, save to a watched directory.
- **PDF library.** Convert a folder of PDF reference docs to searchable markdown.
- **Web research.** Save web pages as HTML, batch convert to markdown for indexing.
- **Legacy docs.** Convert old RTF, ODT, or DOCX files from shared drives.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/converter/formats` | List supported formats and tool availability |
| POST | `/api/converter/convert` | Start batch conversion |
| GET | `/api/converter/status` | Conversion progress |
| POST | `/api/converter/cancel` | Cancel running conversion |

## Converting Files

```json
POST /api/converter/convert
{
  "source_dir": "/home/user/downloads/google-takeout/docs",
  "dest_dir": "/home/user/knowledge_docs/imported",
  "formats": ["docx", "pdf"]
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `source_dir` | yes | Directory containing files to convert |
| `dest_dir` | yes | Destination for markdown output (should be a watched source directory) |
| `formats` | no | Limit to specific formats. Omit to convert all supported types. |

The converter preserves subdirectory structure — files in `source_dir/subdir/file.docx` produce `dest_dir/subdir/file.md`.

## Workflow

1. Gather source files (Google Takeout export, PDF folder, saved web pages)
2. Call `POST /api/converter/convert` with source and destination paths
3. Poll `GET /api/converter/status` for progress
4. Converted markdown appears in the destination directory
5. If the destination is a watched source directory, MarkdownKB auto-indexes the new files

## Configuration

```yaml
plugins:
  converter:
    enabled: true
```

## Dependencies

- **Pandoc** (system package) — the conversion engine
- **poppler-utils** (optional system package) — provides `pdftotext` for better PDF handling
