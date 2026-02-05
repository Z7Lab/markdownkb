# Running Ollama on a Separate Machine

mdkb doesn't run LLMs locally — it calls them over the network. This guide sets up Ollama on a separate machine (e.g. a Mac Mini, a GPU server, etc.) so mdkb can use it.

---

## On the Ollama Machine

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a Model

```bash
ollama pull llama3
# or other models:
# ollama pull mistral
# ollama pull codellama
# ollama pull deepseek-coder-v2
```

### 3. Allow Network Access

By default Ollama only listens on `127.0.0.1`. To allow connections from your mdkb machine, set the host to `0.0.0.0`:

**macOS (launchd):**
```bash
launchctl setenv OLLAMA_HOST "0.0.0.0"
# Then restart Ollama (quit from menu bar and reopen)
```

**Linux (systemd):**
```bash
sudo systemctl edit ollama
```

Add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

Then restart:
```bash
sudo systemctl restart ollama
```

**Or just run it directly:**
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### 4. Verify It's Listening

From the Ollama machine itself:
```bash
curl http://localhost:11434/api/tags
```

From your mdkb machine (replace `<your-docker-host-ip>` with the Ollama machine's IP):
```bash
curl http://<your-docker-host-ip>:11434/api/tags
```

You should see a JSON list of your pulled models.

---

## On the mdkb Machine

### Option A: Edit `config/settings.yaml`

```yaml
llm:
  providers:
    - name: ollama
      model: ollama/llama3
      api_key: ""
      api_base: "http://<your-docker-host-ip>:11434"
  active_provider: ollama
```

Replace `<your-docker-host-ip>` with your Ollama machine's IP or hostname.

### Option B: Use the mdkb Settings UI

1. Open mdkb in your browser (`http://localhost:9713`)
2. Go to the **Settings** tab
3. Set active provider to `ollama`

### Option C: Environment Variable

```bash
OLLAMA_API_BASE=http://<your-docker-host-ip>:11434 python -m app
```

---

## Finding the Ollama Machine's IP

```bash
# On the Ollama machine, run:
# macOS
ipconfig getifaddr en0

# Linux
hostname -I | awk '{print $1}'
```

If both machines are on the same network, use the local IP (usually `192.168.x.x` or `10.x.x.x`).

If you gave the machine a hostname (e.g. `mac-mini.local`), you can use that instead:
```yaml
api_base: "http://mac-mini.local:11434"
```

---

## Using Multiple Providers (Fallback Chain)

mdkb tries providers in order. If one fails, it falls back to the next:

```yaml
llm:
  providers:
    - name: anthropic
      model: anthropic/claude-sonnet-4-20250514
      api_key: "sk-ant-PLACEHOLDER"
      api_base: ""
    - name: ollama
      model: ollama/llama3
      api_key: ""
      api_base: "http://<your-docker-host-ip>:11434"
  active_provider: anthropic
```

If Anthropic is down or you're out of credits, mdkb automatically falls back to your Ollama instance.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` | Ollama isn't running, or `OLLAMA_HOST` isn't set to `0.0.0.0` |
| `No route to host` | Wrong IP, or machines aren't on the same network |
| `Model not found` | Run `ollama pull <model>` on the Ollama machine |
| Slow responses | Expected for large models on CPU. Use smaller models like `phi3` or `mistral` |
| Firewall blocking | Open port `11434` — `sudo ufw allow 11434` (Linux) |

## Recommended Models

| Model | Size | Good For |
|-------|------|----------|
| `llama3` | 4.7GB | General purpose, good quality |
| `mistral` | 4.1GB | Fast, good for chat |
| `codellama` | 3.8GB | Code-focused tasks |
| `phi3` | 2.3GB | Lightweight, fast on CPU |
| `deepseek-coder-v2` | 8.9GB | Best for code, needs more RAM |
