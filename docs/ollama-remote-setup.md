# Running Ollama on a Separate Machine

mdkb doesn't run LLMs locally — it calls them over the network. This guide sets up Ollama on a separate machine (e.g. a Mac Mini, a GPU server, etc.) so mdkb can use it.

**Tested on:** Snapdragon X Elite ARM64 laptop, Ubuntu/Debian, 32GB RAM, CPU-only.

---

## On the Ollama Machine

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux (detects ARM64/aarch64 automatically)
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:
```bash
ollama --version
```

### 2. Get Models

#### Option A: Pull directly (if your connection is reliable)

```bash
ollama pull llama3
```

#### Option B: Manual GGUF from Hugging Face (recommended if pulls time out)

Download the GGUF file from Hugging Face (via browser or `wget`) and place it in your models directory (e.g. `/home/user/llms`).

**Recommended download for code-focused, CPU-only (ARM64, 32GB RAM):**

[DeepSeek-Coder-V2-Lite-Instruct Q6_K](https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF/blob/main/DeepSeek-Coder-V2-Lite-Instruct-Q6_K.gguf) — 14.1GB, single file, from bartowski.

This is a 16B param MoE model with only 2.4B active parameters at inference, so it runs fast on CPU despite the parameter count. Q6_K is very close to Q8_0 quality in practice.

Download via browser or:
```bash
cd /home/user/llms
wget https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF/resolve/main/DeepSeek-Coder-V2-Lite-Instruct-Q6_K.gguf
```

Create a Modelfile pointing to the GGUF:
```bash
echo 'FROM /home/user/llms/DeepSeek-Coder-V2-Lite-Instruct-Q6_K.gguf' > /home/user/llms/Modelfile-deepseek-coder-v2
```

Register it with Ollama:
```bash
ollama create deepseek-coder-v2 -f /home/user/llms/Modelfile-deepseek-coder-v2
```

The `gathering model components` output will repeat many times for large files — this is normal. It should end with `success`.

Verify:
```bash
ollama list
```

**Additional model: Qwen3-8B (general purpose, RAG, reasoning)**

Qwen3-8B is a dense 8B model with thinking/non-thinking mode switching. Great for general RAG, reasoning, and multilingual tasks.

**Recommended: Q4_K_M (5.03GB)** — benefits from ARM Q4 acceleration on Snapdragon, runs faster than Q8_0, and avoids thinking mode repetition loops. See [ARM-specific Q4_0 acceleration](#arm-specific-q40-acceleration) and [Qwen3 thinking mode issues](#qwen3-thinking-mode-issues-and-fix) below.

[Qwen3-8B Q4_K_M](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf) — 5.03GB, single file, from the official Qwen repo.

Download:
```bash
cd /home/user/llms
wget https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf
```

Create a Modelfile with `/no_think` (prevents thinking mode repetition loops) and register:
```bash
echo 'FROM /home/user/llms/Qwen3-8B-Q4_K_M.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.5
SYSTEM "You are a helpful assistant. /no_think"' > /home/user/llms/Modelfile-qwen3-8b-q4

ollama create qwen3:8b-q4_k_m -f /home/user/llms/Modelfile-qwen3-8b-q4
```

**Alternative: Q8_0 (8.71GB)** — near-lossless quality but slower on ARM and prone to thinking mode loops. Only recommended if you need maximum quality and can tolerate slower inference.

[Qwen3-8B Q8_0](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q8_0.gguf) — 8.71GB, single file, from the official Qwen repo.

Download:
```bash
cd /home/user/llms
wget https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q8_0.gguf
```

Create a Modelfile and register (same `/no_think` fix):
```bash
echo 'FROM /home/user/llms/Qwen3-8B-Q8_0.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.5
SYSTEM "You are a helpful assistant. /no_think"' > /home/user/llms/Modelfile-qwen3-8b

ollama create qwen3:8b-q8_0 -f /home/user/llms/Modelfile-qwen3-8b
```

Verify both models are registered:
```bash
ollama list
```

**Note:** If you change `OLLAMA_MODELS` in the systemd config (Step 3), you'll need to re-register models with `ollama create` since the manifests are stored per-directory. The GGUF file itself is not copied — Ollama just creates a reference to it.

### 3. Allow Network Access

By default Ollama only listens on `127.0.0.1`. To allow connections from your mdkb machine, set the host to `0.0.0.0`.

#### Linux (systemd) — with custom models directory

```bash
sudo systemctl edit ollama
```

Add (adjust the models path to match your setup):
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_MODELS=/home/user/llms"
```

##### Fix permissions (important!)

The Ollama systemd service runs as the `ollama` user. It needs:

1. **Traverse permission** on the parent directory of your models folder:
```bash
chmod o+x /home/user
```

2. **Read/write access** to the models directory itself:
```bash
sudo chown -R user:ollama /home/user/llms
sudo chmod -R 775 /home/user/llms
```

This makes both your user and the `ollama` service able to read/write the models directory.

Then restart:
```bash
sudo systemctl restart ollama
```

Verify it's listening on all interfaces:
```bash
ss -tlnp | grep 11434
# Should show 0.0.0.0:11434
```

If it's not running, check for errors:
```bash
sudo systemctl status ollama
journalctl -u ollama --no-pager -n 10
```

#### macOS (launchd)

```bash
launchctl setenv OLLAMA_HOST "0.0.0.0"
# Then restart Ollama (quit from menu bar and reopen)
```

#### Or just run it directly

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### 4. Verify It's Listening

From the Ollama machine itself:
```bash
curl http://localhost:11434/api/tags
```

From your mdkb machine (replace with the Ollama machine's IP):
```bash
curl http://<your-server-ip>:11434/api/tags
```

You should see a JSON list of your models.

---

## On the mdkb Machine

### Option A: Edit `config/settings.yaml`

```yaml
llm:
  providers:
    - name: ollama
      model: ollama/deepseek-coder-v2
      api_key: ""
      api_base: "http://<your-server-ip>:11434"
  active_provider: ollama
```

Replace the IP with your Ollama machine's IP or hostname.

### Option B: Use the mdkb Settings UI

1. Open mdkb in your browser (`http://localhost:9713`)
2. Go to the **Settings** tab
3. Set active provider to `ollama`

### Option C: Environment Variable

```bash
OLLAMA_API_BASE=http://<your-server-ip>:11434 python -m app
```

---

## Finding the Ollama Machine's IP

```bash
# macOS
ipconfig getifaddr en0

# Linux
hostname -I | awk '{print $1}'
```

If both machines are on the same network, use the local IP (usually `192.168.x.x` or `10.x.x.x`).

If you gave the machine a hostname (e.g. `your-server.local`), you can use that instead:
```yaml
api_base: "http://your-server.local:11434"
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
      model: ollama/deepseek-coder-v2
      api_key: ""
      api_base: "http://<your-server-ip>:11434"
  active_provider: anthropic
```

If Anthropic is down or you're out of credits, mdkb automatically falls back to your Ollama instance.

---

## Benchmarking Models (tokens/sec)

Test a model's speed with a single curl command:

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "deepseek-coder-v2",
  "prompt": "Write a Python function that reads a CSV and returns top 5 rows sorted by a column.",
  "stream": false
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
print(f'Tokens generated: {d[\"eval_count\"]}')
print(f'Tokens/sec: {tps:.2f}')
print(f'Response:\n{d[\"response\"]}')
"
```

Swap the model name to test different models. The response JSON includes `eval_count` (tokens generated) and `eval_duration` (nanoseconds). The formula: `tokens/sec = eval_count / (eval_duration / 1e9)`.

**Note:** First run after loading a model will be slower (model load into RAM). Use `OLLAMA_KEEP_ALIVE=24h` to keep models loaded between requests (see Performance Optimization below).

For a quick interactive test:
```bash
ollama run deepseek-coder-v2
# Type a message and hit enter. /bye to exit.
```

---

## Performance Optimization (CPU-only, Snapdragon X Elite)

### Optimized systemd override

The full optimized override for a 12-core Snapdragon X Elite with 32GB RAM:

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_MODELS=/home/user/llms"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_KEEP_ALIVE=24h"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_NUM_THREADS=10"
```

Then:
```bash
sudo systemctl restart ollama
```

### What each setting does

| Setting | Value | Why |
|---------|-------|-----|
| `OLLAMA_FLASH_ATTENTION=1` | Enabled | Reduces memory usage, enables KV cache quantization |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | 8-bit cache | Halves KV cache memory vs default f16, negligible quality loss |
| `OLLAMA_KEEP_ALIVE=24h` | 24 hours | Keeps model loaded in RAM — avoids reload cost between requests |
| `OLLAMA_MAX_LOADED_MODELS=1` | 1 model | Single model at a time — safe for 32GB RAM |
| `OLLAMA_NUM_PARALLEL=1` | 1 request | Single user, no need to split resources |
| `OLLAMA_NUM_THREADS=10` | 10 of 12 cores | Leaves 2 cores for OS and other tasks |

These settings benefit **all** quantization levels (Q4_0, Q6_K, Q8_0, etc.).

### ARM-specific Q4_0 acceleration

On Snapdragon X Elite, **Q4_0 quantizations get additional ARM-specific GEMM/GEMV acceleration** built into llama.cpp (which Ollama uses). This fast path activates automatically when ARM hardware + Q4_0 format is detected — no special builds or settings needed.

This makes Q4_0 models disproportionately fast on Snapdragon compared to other quant levels (comparable to Apple M2 with Metal GPU acceleration). The tradeoff is slightly lower quality vs Q6_K/Q8_0.

If speed is a priority, consider grabbing Q4_0 versions of your models as well:
- [Qwen3-8B Q4_K_M](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf) — 5.03GB
- [DeepSeek-Coder-V2-Lite-Instruct Q4_K_M](https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF) — 10.4GB

### Qwen3 thinking mode: issues and fix

Qwen3 models have a "thinking mode" that generates a `<think>` reasoning chain before the actual response. **On quantized ARM inference (Q8_0 and sometimes Q4_K_M), this causes a repetition loop** — the model gets stuck repeating its thinking chain endlessly. Symptoms:

- `ollama run` shows the same paragraph repeating over and over
- `stream: false` curl requests hang for 3+ minutes with no response (the model is generating an infinite think chain)
- Cancelled requests can leave the model in a stuck state requiring `sudo systemctl restart ollama`

**Fix: Disable thinking by default via Modelfile**

Create a Modelfile that disables thinking mode and adds repeat penalty:

```bash
echo 'FROM /home/user/llms/Qwen3-8B-Q4_K_M.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.5
SYSTEM "You are a helpful assistant. /no_think"' > /home/user/llms/Modelfile-qwen3-8b-q4

ollama create qwen3:8b-q4_k_m -f /home/user/llms/Modelfile-qwen3-8b-q4
```

The `/no_think` in the system prompt disables thinking by default. Users can still enable it per-message by appending `/think` to a prompt when needed.

**For Q8_0 (if you keep it):**
```bash
echo 'FROM /home/user/llms/Qwen3-8B-Q8_0.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.5
SYSTEM "You are a helpful assistant. /no_think"' > /home/user/llms/Modelfile-qwen3-8b

ollama create qwen3:8b-q8_0 -f /home/user/llms/Modelfile-qwen3-8b
```

### Thinking mode vs /no_think for RAG

For RAG workloads, **thinking mode is not recommended**. The model's job in RAG is to read the retrieved context and give a clear, grounded answer — not to reason through a problem from scratch.

Thinking mode hurts RAG because:
- It wastes tokens "reasoning" about the context instead of just answering
- It's slower (which matters for interactive chat)
- It's prone to repetition loops on quantized ARM inference

**Recommended setup for mdkb:**
- **DeepSeek-Coder-V2** — code-related queries, fast, no thinking mode
- **Qwen3-8B in `/no_think` mode** — general RAG/chat, fast direct answers grounded in retrieved context

If you ever need thinking for a specific hard question, append `/think` to that one message — the system prompt default just sets `/no_think` as the baseline.

---

## Removing Models

### Unregister only (keep the GGUF file on disk)

This removes the model from `ollama list` but leaves the downloaded GGUF file intact so you can re-register it later without re-downloading:

```bash
ollama rm <model-name>
# e.g. ollama rm qwen3:8b-q8_0
```

To re-register later, just run `ollama create` with the Modelfile again.

### Fully remove (unregister + delete GGUF)

To also free up disk space, delete the GGUF file after unregistering:

```bash
ollama rm <model-name>
rm /home/user/llms/<filename>.gguf
# e.g.
# ollama rm qwen3:8b-q8_0
# rm /home/user/llms/Qwen3-8B-Q8_0.gguf
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` | Ollama isn't running, or `OLLAMA_HOST` isn't set to `0.0.0.0` |
| `permission denied: ensure path elements are traversable` | The `ollama` user can't access the models directory. Check `chmod o+x` on parent dirs and `chown`/`chmod` on the models dir (see Step 3) |
| `No route to host` | Wrong IP, or machines aren't on the same network |
| `Model not found` | Run `ollama pull <model>` or register your GGUF with `ollama create` |
| Slow responses | Expected for large models on CPU. Use smaller models or lower quantization |
| Firewall blocking | Open port `11434` — `sudo ufw allow 11434` (Linux) |
| `ollama pull` times out | Download GGUF manually from Hugging Face and use `ollama create` (see Step 2, Option B) |
| Qwen3 repeating/looping output | Thinking mode repetition loop. Use a Modelfile with `/no_think` system prompt and `repeat_penalty 1.5` (see [Qwen3 thinking mode fix](#qwen3-thinking-mode-issues-and-fix)) |
| `stream: false` request hangs for minutes | Likely Qwen3 generating an infinite think chain. Cancel with Ctrl+C, restart Ollama, and use `/no_think` |
| Model stuck after cancelled request | The previous request may still be running. Force clean: `sudo systemctl stop ollama && sudo killall ollama && sleep 2 && sudo systemctl start ollama` |

## Recommended Models (CPU-only, 32GB RAM)

| Model | Size | Quantization | Good For |
|-------|------|--------------|----------|
| `deepseek-coder-v2` (Lite 16B, MoE) | 14.1GB | Q6_K | **Code-focused, fast on CPU (2.4B active params). No thinking mode.** |
| `qwen3:8b-q4_k_m` | 5.03GB | Q4_K_M | **General RAG, reasoning, multilingual.** ARM Q4 acceleration, needs `/no_think` Modelfile |
| `qwen3:8b-q8_0` | 8.71GB | Q8_0 | General RAG, near-lossless quality. Slower on ARM, needs `/no_think` Modelfile |
| `llama3` | 4.7GB | Q4_K_M | General purpose, good quality |
| `mistral` | 4.1GB | Q4_K_M | Fast, good for chat |
| `phi3` | 2.3GB | Q4_K_M | Lightweight, fastest on CPU |

Both `deepseek-coder-v2` (14.1GB) and `qwen3:8b-q4_k_m` (5.03GB) fit comfortably on 32GB RAM (~19GB total). Ollama loads one model at a time by default.

**For mdkb RAG workloads:** Use DeepSeek-Coder-V2 for code queries and Qwen3-8B Q4_K_M (with `/no_think`) for general chat. Thinking mode is not recommended for RAG — see [Thinking mode vs /no_think for RAG](#thinking-mode-vs-no_think-for-rag).
