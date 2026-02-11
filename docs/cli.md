# CLI

mdkb includes a command-line interface for indexing and search without starting the web server.

```bash
python -m app.cli <command> [options]
```

Use `--config path/to/settings.yaml` to override the default config location.

## Commands

### index

Index all configured source directories.

```bash
python -m app.cli index
```

### search

Semantic search against the knowledge base.

```bash
python -m app.cli search "your query here"
python -m app.cli search "fastapi routing" -k 10
```

| Flag | Description |
|------|-------------|
| `query` | Search query (required) |
| `-k` | Number of results (default: from settings.yaml `retrieval.top_k`) |

### add-source

Add a source directory to the configuration and save.

```bash
python -m app.cli add-source /path/to/docs
```

### stats

Display index statistics: configured sources, file count, chunk count, embedding model, and active LLM provider.

```bash
python -m app.cli stats
```
