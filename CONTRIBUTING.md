# Contributing to MarkdownKB

## Dev environment

**Prerequisites**: Python 3.11+, Node 18+.

```bash
git clone <repo-url>
cd mdkb
cp config/settings.yaml.example config/settings.yaml
./run.sh          # creates .venv, installs deps, starts backend:9713 + Vite:5173
```

## Running tests

```bash
.venv/bin/pytest              # full test suite
.venv/bin/pytest tests/test_api.py  # single file
```

Frontend type-check:

```bash
cd frontend && npm run build
```

## Building with Docker

```bash
make docker-build
make docker-up
```

See the Makefile (`make help`) for all available targets.

## Plugin development

Plugins are self-contained directories under `app/plugins/`. See [docs/how-to/plugin-development.md](docs/how-to/plugin-development.md) for the full plugin contract: structure, manifests, lifecycle hooks, databases, and MCP tool registration.

## Pull requests

- One logical change per PR.
- Include tests for new behaviour — `tests/` uses `pytest` + `httpx.AsyncClient`.
- Update docs in `docs/` if your change affects user-facing behaviour. Reference doc that needs updating is usually obvious from the area you changed; see [docs/README.md](docs/README.md) for the full index.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — do not open a public issue for vulnerabilities.
