# Running Ollama on a Separate Machine

mdkb doesn't run LLMs locally — it calls them over the network. This guide sets up Ollama on a separate machine so mdkb can use it. Works with any hardware: Mac Mini, GPU server, ARM SBC, dedicated Linux box, etc.

---

## Security Considerations

Ollama has **no built-in authentication**. Anyone who can reach port 11434 can query your models, list them, pull new ones, or delete them. Before exposing Ollama to the network, choose a security approach.

### Recommended: SSH Tunnel (most secure)

Keep Ollama on localhost (the default) and create an encrypted tunnel from the mdkb machine:

```bash
# On the mdkb machine — forward local port 11434 to the Ollama machine
ssh -N -L 11434:localhost:11434 user@ollama-machine
```

Then configure mdkb to use `http://localhost:11434` — traffic is encrypted and authenticated via SSH. No ports need to be opened on the Ollama machine.

To make the tunnel persistent, create a systemd service:

```bash
sudo tee /etc/systemd/system/ollama-tunnel.service > /dev/null << 'EOF'
[Unit]
Description=SSH tunnel to Ollama server
After=network-online.target
Wants=network-online.target

[Service]
User=YOUR_USER
ExecStart=/usr/bin/ssh -N -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes -L 11434:localhost:11434 user@ollama-machine
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ollama-tunnel
```

Replace `YOUR_USER` and `user@ollama-machine` with your actual values. Use SSH key authentication (no password prompts).

### Alternative: Firewall Allowlist

If an SSH tunnel is impractical, bind Ollama to `0.0.0.0` (Step 3 below) but restrict access to only the mdkb machine's IP:

```bash
# Allow only your mdkb machine (replace with its actual IP)
sudo ufw allow from 192.168.x.x to any port 11434 proto tcp

# Block everyone else
sudo ufw deny 11434

sudo ufw reload
```

Or with iptables:
```bash
iptables -A INPUT -p tcp --dport 11434 -s 192.168.x.x -j ACCEPT
iptables -A INPUT -p tcp --dport 11434 -j DROP
```

### What to Avoid

- **Don't** run `sudo ufw allow 11434` without an IP restriction — this opens Ollama to your entire network (and the internet, if the machine has a public IP).
- **Don't** expose Ollama on a public-facing server without a reverse proxy that adds authentication.
- **Don't** use Ollama over untrusted networks without encryption (SSH tunnel or TLS reverse proxy).

---

## On the Ollama Machine

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux (detects ARM64/x86_64 automatically)
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:
```bash
ollama --version
```

### 2. Get Models

#### Option A: Pull directly

```bash
ollama pull llama3
```

#### Option B: Manual GGUF from Hugging Face

If `ollama pull` is slow or times out, download the GGUF file directly and register it manually. This also lets you pick a specific quantization level.

Download the GGUF file (via browser or `wget`) and place it in a models directory:

```bash
mkdir -p ~/llms
cd ~/llms
wget <HUGGINGFACE_GGUF_URL>
```

Create a Modelfile pointing to the GGUF:
```bash
echo 'FROM ~/llms/your-model.gguf' > ~/llms/Modelfile-your-model
```

Register it with Ollama:
```bash
ollama create your-model -f ~/llms/Modelfile-your-model
```

The `gathering model components` output will repeat for large files — this is normal. It should end with `success`.

Verify:
```bash
ollama list
```

**Note:** If you change `OLLAMA_MODELS` in the systemd config (Step 3), you'll need to re-register models with `ollama create` since the manifests are stored per-directory. The GGUF file itself is not copied — Ollama just creates a reference to it.

### 3. Allow Network Access

By default Ollama only listens on `127.0.0.1`. To allow connections from your mdkb machine, set the host to `0.0.0.0`.

#### Linux (systemd)

```bash
sudo systemctl edit ollama
```

Add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

If you're using a custom models directory, also add:
```ini
Environment="OLLAMA_MODELS=/path/to/your/models"
```

##### Fix permissions (if using custom models directory)

The Ollama systemd service runs as the `ollama` user. It needs:

1. **Traverse permission** on the parent directory of your models folder:
```bash
chmod o+x /home/your-user
```

2. **Read/write access** to the models directory itself:
```bash
sudo chown -R your-user:ollama /path/to/models
sudo chmod -R 775 /path/to/models
```

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
curl http://<OLLAMA_IP>:11434/api/tags
```

You should see a JSON list of your models.

---

## On the mdkb Machine

### Option A: Edit `config/settings.yaml`

```yaml
llm:
  providers:
    - name: ollama
      model: ollama/llama3
      api_base: "http://<OLLAMA_IP>:11434"
  active_provider: ollama
```

Replace `<OLLAMA_IP>` with your Ollama machine's IP or hostname.

### Option B: Use the mdkb Settings UI

1. Open mdkb in your browser (`http://localhost:9713`)
2. Go to the **Settings** tab
3. Set active provider to `ollama`

### Option C: Environment Variable

```bash
OLLAMA_API_BASE=http://<OLLAMA_IP>:11434 python -m app
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

If you gave the machine a hostname (e.g. `ollama-box.local`), you can use that instead:
```yaml
api_base: "http://ollama-box.local:11434"
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
      api_base: "http://<OLLAMA_IP>:11434"
  active_provider: anthropic
```

If Anthropic is down or you're out of credits, mdkb automatically falls back to your Ollama instance.

---

## Benchmarking Models

Test a model's speed with a single curl command:

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "llama3",
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

The response JSON includes `eval_count` (tokens generated) and `eval_duration` (nanoseconds). Formula: `tokens/sec = eval_count / (eval_duration / 1e9)`.

**Note:** First run after loading a model will be slower (model load into RAM). Use `OLLAMA_KEEP_ALIVE=24h` to keep models loaded between requests.

For a quick interactive test:
```bash
ollama run llama3
# Type a message and hit enter. /bye to exit.
```

---

## Performance Tuning

### Ollama Environment Variables

These settings improve performance for single-user setups. Add them via `sudo systemctl edit ollama` (Linux) or `launchctl setenv` (macOS):

| Setting | Value | Why |
|---------|-------|-----|
| `OLLAMA_FLASH_ATTENTION=1` | Enabled | Reduces memory usage, enables KV cache quantization |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | 8-bit cache | Halves KV cache memory vs default f16, negligible quality loss |
| `OLLAMA_KEEP_ALIVE=24h` | 24 hours | Keeps model loaded in RAM — avoids reload cost between requests |
| `OLLAMA_MAX_LOADED_MODELS=1` | 1 model | Single model at a time — prevents memory pressure |
| `OLLAMA_NUM_PARALLEL=1` | 1 request | Single user, no need to split resources |
| `OLLAMA_NUM_THREADS=N` | CPU cores - 2 | Leave headroom for the OS. E.g. 10 for a 12-core machine |

These settings benefit all quantization levels (Q4_0, Q6_K, Q8_0, etc.).

### CPU-Only Inference

If your Ollama machine has no GPU, model choice and quantization level matter a lot:

- **MoE models** (e.g. DeepSeek-Coder-V2 Lite — 16B params, 2.4B active) are excellent for CPU inference. Only a fraction of parameters are active per token, so they run much faster than their total parameter count suggests.
- **Smaller dense models** (7-8B params, Q4_K_M quantization) give the best speed/quality tradeoff for CPU-only setups.
- **Q4_K_M** is generally the sweet spot — ~40% smaller than Q8_0 with minimal quality loss.
- **Q8_0** is near-lossless quality but slower and uses more RAM.

### ARM Processors

ARM chips (Apple M-series, Snapdragon X, Ampere) are particularly good at CPU-only LLM inference because llama.cpp (which Ollama uses) has optimized ARM NEON/SVE kernels. Q4_0 quantizations specifically get hardware-accelerated GEMM/GEMV on ARM, making them disproportionately fast.

If you're running on ARM hardware, consider Q4_K_M or Q4_0 quantizations for the best performance.

### GPU Acceleration

If your Ollama machine has a GPU, Ollama will use it automatically (CUDA for NVIDIA, Metal for Apple). GPU inference is significantly faster — most models will run well at higher quantization levels (Q6_K, Q8_0) without the speed concerns of CPU-only setups.

### Qwen3 Thinking Mode

Qwen3 models have a "thinking mode" that generates a `<think>` reasoning chain before responding. This can cause issues:

- **Repetition loops** on some quantization levels — the model gets stuck repeating its thinking chain.
- **Slow responses** — thinking wastes tokens on internal reasoning instead of answering.
- **Not useful for RAG** — the model's job in RAG is to read context and answer, not reason from scratch.

**Fix:** Disable thinking by default in the Modelfile:

```bash
echo 'FROM /path/to/Qwen3-8B-Q4_K_M.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.5
SYSTEM "You are a helpful assistant. /no_think"' > ~/llms/Modelfile-qwen3

ollama create qwen3:8b -f ~/llms/Modelfile-qwen3
```

The `/no_think` system prompt disables thinking by default. Users can still enable it per-message by appending `/think` to a prompt when needed.

---

## Removing Models

### Unregister only (keep the GGUF file on disk)

```bash
ollama rm <model-name>
```

This removes the model from `ollama list` but leaves the GGUF file intact. Re-register later with `ollama create`.

### Fully remove (unregister + delete GGUF)

```bash
ollama rm <model-name>
rm ~/llms/<filename>.gguf
```

---

## Recommended Models

| Model | Size | Good For |
|-------|------|----------|
| `llama3` (8B) | 4.7GB | General purpose, good all-rounder |
| `qwen3:8b` | 5-9GB | General RAG, reasoning, multilingual. Use `/no_think` Modelfile |
| `deepseek-coder-v2` (Lite 16B MoE) | 10-14GB | Code-focused, fast on CPU (only 2.4B active params) |
| `mistral` (7B) | 4.1GB | Fast, good for chat |
| `phi3` (3.8B) | 2.3GB | Lightweight, fastest on CPU |

**For mdkb RAG workloads**, thinking mode is generally not recommended — the model should read the retrieved context and give a grounded answer, not reason from scratch. Use `/no_think` with Qwen3.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` | Ollama isn't running, or `OLLAMA_HOST` isn't set to `0.0.0.0` |
| `permission denied: ensure path elements are traversable` | The `ollama` user can't access the models directory. Check `chmod o+x` on parent dirs and `chown`/`chmod` on the models dir (see Step 3) |
| `No route to host` | Wrong IP, or machines aren't on the same network |
| `Model not found` | Run `ollama pull <model>` or register your GGUF with `ollama create` |
| Slow responses | Expected for large models on CPU. Try smaller models or lower quantization |
| Firewall blocking | Allow only your mdkb machine's IP — see [Security Considerations](#security-considerations) |
| `ollama pull` times out | Download GGUF manually from Hugging Face and use `ollama create` (see Step 2, Option B) |
| Qwen3 repeating/looping output | Thinking mode issue. Use a Modelfile with `/no_think` and `repeat_penalty 1.5` (see [Qwen3 Thinking Mode](#qwen3-thinking-mode)) |
| Request hangs for minutes | Likely an infinite think chain. Cancel, restart Ollama, and use `/no_think` |
| Model stuck after cancelled request | Force clean: `sudo systemctl stop ollama && sudo killall ollama && sleep 2 && sudo systemctl start ollama` |
