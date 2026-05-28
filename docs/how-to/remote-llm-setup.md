# Connecting MarkdownKB to Remote LLM Servers

This guide explains how to run MarkdownKB in Docker on one machine while connecting to LLM servers (Ollama, llama.cpp, LM Studio, vLLM, or any OpenAI-compatible server) running on another machine.

---

## Architecture Overview

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Docker Host Machine    │         │  LLM Server Machine      │
│                         │         │                          │
│  ┌────────────────┐    │  HTTP   │  ┌─────────────────┐    │
│  │ markdownkb     │────┼────────>│  │ Ollama          │    │
│  │                │    │  :11434 │  │ (port 11434)    │    │
│  │ - Frontend     │    │         │  └─────────────────┘    │
│  │ - Backend/RAG  │    │    OR   │                          │
│  │ - Vector DB    │    │  :8080  │  ┌─────────────────┐    │
│  └────────────────┘    │────────>│  │ llama.cpp       │    │
│                         │         │  │ (port 8080)     │    │
└─────────────────────────┘         │  └─────────────────┘    │
                                    │                          │
                                    │  GGUF Models Storage     │
                                    └──────────────────────────┘
```

**Key points:**
- MarkdownKB runs in Docker and only needs network access to the LLM server
- The LLM server handles all model inference
- MarkdownKB stores embeddings/vector DB locally
- Works with both Ollama and llama.cpp servers

---

## LLM Server Setup

Choose **either** Ollama or llama.cpp on your LLM server machine.

### Option 1: Using Ollama

**Install Ollama:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Enable network access:**
```bash
sudo systemctl edit ollama
```

Add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

**Restart:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Pull a model:**
```bash
ollama pull deepseek-coder-v2:latest
# or
ollama pull qwen3:8b
```

**Verify it's listening:**
```bash
ss -tlnp | grep 11434
# Should show: 0.0.0.0:11434

# Test locally
curl http://localhost:11434/api/tags
```

**Get server IP:**
```bash
hostname -I | awk '{print $1}'
# Example: <your-server-ip>
```

### Option 2: Using llama.cpp

**Build llama.cpp:**
```bash
cd ~
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON
cmake --build build --config Release --target llama-server -j$(nproc)
```

**Download GGUF model:**
```bash
mkdir -p ~/llms
cd ~/llms
wget https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF/resolve/main/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf
```

**Run llama-server:**
```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/llms/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -t 6 \
  --num-ctx 16384 \
  --parallel 1 \
  -fa on
```

**Test:**
```bash
curl http://localhost:8080/health
# Response: {"status":"ok"}
```

---

## MarkdownKB Docker Setup

### 1. Configure Connection to Remote LLM

**Configure in `config/settings.yaml` (for first-run seed) or via **Settings → Chat Model** after first run:**

#### For Ollama:

```yaml
llm:
  providers:
  - name: ollama
    model: ollama/deepseek-coder-v2:latest
    api_key: ''
    api_base: http://<your-server-ip>:11434  # Replace with your LLM server IP
  active_provider: ollama
  temperature: 0.3
  max_tokens: 4096

# Retrieval settings (optimized for 16k context)
retrieval:
  top_k: 10
  score_threshold: 0.25
  hybrid_search: true
  bm25_weight: 0.5
```

#### For llama.cpp:

```yaml
llm:
  providers:
  - name: llamacpp
    model: openai/deepseek  # "openai/" prefix for OpenAI-compatible APIs
    api_key: 'dummy'        # Not used, but required for OpenAI-compatible providers
    api_base: http://<your-server-ip>:8080/v1  # Note the /v1 suffix!
  active_provider: llamacpp
  temperature: 0.3
  max_tokens: 4096
```

#### Both (with fallback):

```yaml
llm:
  providers:
  - name: ollama
    model: ollama/deepseek-coder-v2:latest
    api_key: ''
    api_base: http://<your-server-ip>:11434  # Replace with your LLM server IP

  - name: llamacpp
    model: openai/deepseek
    api_key: 'dummy'
    api_base: http://<your-server-ip>:8080/v1  # Replace with your LLM server IP

  active_provider: ollama  # Switch to "llamacpp" to use llama.cpp
```

### 2. Environment Variables (Optional)

**Create `.env` file:**
```bash
cp .env.example .env
```

**Edit `.env`:**
```bash
# markdownkb ports
API_PORT=9713
FRONTEND_PORT=9714

# Ollama remote server (replace with your LLM server IP)
OLLAMA_API_BASE=http://<your-server-ip>:11434

# Expose to network (optional - defaults to localhost only)
# SERVER_HOST=0.0.0.0
```

**Note:** Environment variables override database values for the settings listed in [Configuration](../reference/configuration.md#precedence).

### 3. Start MarkdownKB

```bash
# First time setup
cp config/settings.yaml.example config/settings.yaml
# Edit settings.yaml with your LLM server IP (used as initial seed on first run)

# Build and start
make docker-build && make docker-up
```

**Access MarkdownKB:**
- Local: http://localhost:9713
- Network (if SERVER_HOST=0.0.0.0): http://<docker-host-ip>:9713

---

## Testing the Connection

### Test 1: From LLM Server (Verify Accessibility)

```bash
# Get server IP
hostname -I | awk '{print $1}'

# Test Ollama
curl http://<server-ip>:11434/api/tags

# Test llama.cpp
curl http://<server-ip>:8080/v1/models
```

### Test 2: From Docker Host (Before Starting MarkdownKB)

```bash
# Test Ollama connection (replace <your-server-ip> with your LLM server IP)
curl http://<your-server-ip>:11434/api/tags

# Quick generation test
curl http://<your-server-ip>:11434/api/generate -d '{
  "model": "deepseek-coder-v2:latest",
  "prompt": "Say hello",
  "stream": false,
  "options": {"num_predict": 20}
}' | jq '.response'
```

### Test 3: Check MarkdownKB Logs

```bash
# View logs
make logs
# or
docker-compose logs -f

# Look for:
# ✓ "Connected to LLM provider: ollama"
# ✓ Successful responses to chat queries
```

### Test 4: Use MarkdownKB UI

1. Open http://localhost:9713
2. Go to **Chat** tab
3. Ask: "How do I use this knowledge base?"
4. Should get a response from the remote LLM

---

## Switching Between Ollama and llama.cpp

**To switch providers:**

Use **Settings → Chat Model → Active Provider** in the web UI. Changes take effect immediately — no restart needed.

**Or use environment variable:**
```bash
# In .env
ACTIVE_LLM_PROVIDER=llamacpp
```

---

## Security Considerations

⚠️ **Exposing LLM server to network has security implications!**

### Option 1: SSH Tunnel (Recommended)

**Instead of exposing ports, use SSH tunnel:**

```bash
# On Docker host machine, create tunnel:
ssh -N -L 11434:localhost:11434 user@llm-server-ip

# Keep this running in background
```

**Then in MarkdownKB config:**
```yaml
api_base: http://localhost:11434  # Goes through tunnel
```

**Make persistent with systemd:**
```bash
sudo tee /etc/systemd/system/ollama-tunnel.service > /dev/null << 'EOF'
[Unit]
Description=SSH tunnel to Ollama server
After=network-online.target

[Service]
User=your-user
ExecStart=/usr/bin/ssh -N -o ServerAliveInterval=60 -L 11434:localhost:11434 user@llm-server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now ollama-tunnel
```

### Option 2: Firewall Allowlist

**On LLM server, allow only Docker host:**

```bash
# Allow only Docker host IP (replace <your-docker-host-ip> with your Docker host IP)
sudo ufw allow from <your-docker-host-ip> to any port 11434 proto tcp

# Block everyone else
sudo ufw deny 11434

sudo ufw reload
```

### Option 3: VPN

Run both machines on a VPN (Tailscale, WireGuard, etc.) for encrypted private network.

---

## Troubleshooting

### Connection Refused

**Symptoms:**
```
Error: Connection refused to http://<your-server-ip>:11434  # example IP — replace with yours
```

**Fixes:**
1. Check server is running: `systemctl status ollama`
2. Check it's listening on network: `ss -tlnp | grep 11434`
3. Check firewall: `sudo ufw status`
4. Ping server: `ping <your-server-ip>`  # replace with your LLM server IP
5. Test from server itself: `curl http://localhost:11434/api/tags`

### Model Not Found

**Symptoms:**
```
Error: Model 'deepseek-coder-v2:latest' not found
```

**Fixes:**
1. List available models: `ollama list`
2. Pull the model: `ollama pull deepseek-coder-v2:latest`
3. Check model name in **Settings → Chat Model** matches exactly

### Slow Responses

**Expected performance:**
- CPU-only inference: 3-8 tok/s
- Network latency: +50-200ms per request
- Total: ~1-2s for short responses

**To improve:**
- Use MoE models (DeepSeek) for 45% faster CPU inference
- Reduce `max_tokens` in **Settings → Chat Model**
- Use lower context (`num_ctx 8192` instead of `16384`)

### MarkdownKB Can't Connect

**Check MarkdownKB logs:**
```bash
docker-compose logs -f backend
```

**Look for:**
- Network errors
- Wrong IP/port
- Authentication failures

**Test manually:**
```bash
# From inside Docker container (replace <your-server-ip> with your LLM server IP)
docker-compose exec backend bash
curl http://<your-server-ip>:11434/api/tags
```

---

## Performance Optimization

### For Remote LLM Server

**Increase context for better RAG:**
```yaml
# In Modelfile (Ollama)
PARAMETER num_ctx 16384  # 16k context

# Or llama.cpp
--num-ctx 16384
```

**Optimize retrieval:**

Configure via **Settings → Retrieval** in the web UI, or seed in `config/settings.yaml` before first run:
```yaml
retrieval:
  top_k: 10              # Retrieve more chunks
  score_threshold: 0.25  # Slightly more permissive
```

### For Network

**Use persistent connections:**
- MarkdownKB already uses HTTP keep-alive
- Reduces connection overhead

**Reduce round-trips:**
- Use streaming for real-time responses
- Batch embeddings when possible

---

## Model Recommendations

| Model | Size | Speed (CPU) | Best For |
|-------|------|-------------|----------|
| DeepSeek-Coder-V2 | 10GB | 5.5 tok/s | Code documentation |
| Qwen3-8B | 5GB | 3.8 tok/s | General purpose |
| Llama 3.1 8B | 5GB | 4.0 tok/s | General purpose |
| Phi-3 Mini | 2.3GB | 8.0 tok/s | Fast but lower quality |

**Recommendation:** DeepSeek-Coder-V2 (Q4_K_M) for code-heavy documentation.

---

## Additional Resources

- [Ollama Remote Setup Guide](../thirdparty/ollama-remote-setup.md)
- [llama.cpp Setup Guide](../thirdparty/llamacpp-setup.md)
- [llama.cpp API Reference](../thirdparty/llamacpp-api.md)
- [Performance Benchmarking](../reference/llm-benchmarking.md)
