# File Converter Plugin

Batch convert documents (DOCX, PDF, PPTX, XLSX, HTML, EPUB, CSV, Jupyter notebooks, Outlook MSG, and more) to markdown using Microsoft's [markitdown](https://github.com/microsoft/markitdown) library. Converted files are saved to a watched source directory where MarkdownKB auto-indexes them.

## No system dependencies

Unlike the previous pandoc-based converter, markitdown is a pure Python library. No external binaries needed — it works out of the box in Docker and native installs.

## Supported formats

| Format | Extensions |
|--------|-----------|
| Microsoft Word | `.docx` |
| PDF | `.pdf` |
| PowerPoint | `.pptx` |
| Excel | `.xlsx`, `.xls` |
| HTML | `.html`, `.htm` |
| EPUB | `.epub` |
| CSV | `.csv` |
| Plain Text | `.txt` |
| reStructuredText | `.rst` |
| Rich Text | `.rtf` |
| LibreOffice | `.odt` |
| Jupyter Notebook | `.ipynb` |
| Outlook Message | `.msg` |

## Usage

1. Enable the plugin in `config/settings.yaml`:
   ```yaml
   plugins:
     converter:
       enabled: true
   ```

2. Convert files via API:
   ```bash
   curl -X POST http://localhost:9713/api/v1/converter/convert \
     -H "Content-Type: application/json" \
     -d '{"source_dir": "/path/to/docs", "dest_dir": "/path/to/output"}'
   ```

3. Check progress:
   ```bash
   curl http://localhost:9713/api/v1/converter/status
   ```

## How it works

1. Scans `source_dir` recursively for files matching supported extensions
2. Converts each file to markdown using markitdown
3. Writes output to `dest_dir` preserving subdirectory structure
4. If the destination is a watched source directory, MarkdownKB auto-indexes the new files
