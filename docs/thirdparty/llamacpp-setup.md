# Building and Running llama.cpp from Source

llama.cpp provides direct, high-performance LLM inference with native CPU optimizations. While Ollama offers convenience, llama.cpp can be faster for CPU-only setups and uses less memory.

---

## Why llama.cpp?

**Advantages over Ollama:**
- Lower memory footprint (3.5GB vs 5.2GB for same model)
- Direct control over optimization flags
- OpenAI-compatible API for easy integration
- No wrapper overhead

**When to use llama.cpp:**
- You want maximum CPU performance
- You need fine-grained control over inference settings
- You're building production systems that need the lowest latency

---

## Prerequisites

Install build tools:
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake git
```

---

## Building from Source with Native Optimizations

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
```

### 2. Configure Build with Native CPU Optimizations

The key to maximum performance is building with `-march=native`, which enables CPU-specific optimizations for your processor (AVX2, AVX512, etc.):

```bash
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON
```

**What `GGML_NATIVE=ON` does:**
- Compiles with `-march=native` flag
- Enables AVX2, AVX512, FMA instructions (if your CPU supports them)
- Optimizes for your specific CPU architecture (e.g., Intel Ice Lake)

### 3. Build llama-server

```bash
cmake --build build --config Release --target llama-server -j$(nproc)
```

This builds only the server component. The binary will be at:
```
~/llama.cpp/build/bin/llama-server
```

**Build time:** 2-3 minutes on an 8-core CPU.

---

## Running llama-server

### Basic Usage

```bash
~/llama.cpp/build/bin/llama-server \
  -m /path/to/model.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -t 6 \
  -c 2048 \
  --parallel 1 \
  -fa on
```

### Important Parameters

| Parameter | Description | Recommended |
|-----------|-------------|-------------|
| `-m` | Path to GGUF model file | Required |
| `--host` | Bind address | `127.0.0.1` (local only) or `0.0.0.0` (network) |
| `--port` | Port number | `8080` |
| `-t` | Thread count | CPU cores - 2 (e.g., 6 for 8-core CPU) |
| `-c` | Context size | `2048` (default), `4096` for longer contexts |
| `--parallel` | Parallel requests | `1` for single user |
| `-fa` | Flash attention | `on` (faster), `off`, or `auto` |

### Example: Running Qwen3-8B

```bash
~/llama.cpp/build/bin/llama-server \
  -m /home/user/llms/Qwen3-8B-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -t 6 \
  -c 2048 \
  --parallel 1 \
  -fa on
```

### Running in the Background

```bash
nohup ~/llama.cpp/build/bin/llama-server \
  -m /home/user/llms/Qwen3-8B-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -t 6 \
  -c 2048 \
  --parallel 1 \
  -fa on \
  > ~/llama-server.log 2>&1 &
```

Check if it's running:
```bash
curl http://localhost:8080/health
# Response: {"status":"ok"}
```

---

## Performance Tuning

### Thread Count Optimization

**Finding the optimal thread count:**
- Start with: `CPU cores - 2`
- For 4-core/8-thread (hyperthreading): Try 4-6 threads
- For 8-core: Try 6-8 threads
- Too many threads = overhead, too few = underutilized

**Test different values:**
```bash
# Test with 4 threads
~/llama.cpp/build/bin/llama-server -m model.gguf -t 4 --port 8080

# Test with 6 threads
~/llama.cpp/build/bin/llama-server -m model.gguf -t 6 --port 8081

# Benchmark both and compare
```

### Flash Attention

Flash attention reduces memory usage and can improve performance:
- `on` - Always use (recommended for Q4/Q8 models)
- `off` - Disable
- `auto` - Let llama.cpp decide

### Context Size

Larger context = more memory + slower inference:
- `2048` - Good for most RAG use cases
- `4096` - Longer conversations
- `8192+` - Long documents (requires more RAM)

---

## Comparing Performance: Ollama vs llama.cpp

Based on benchmarks with Q4_K_M models on Intel i7-1165G7:

| Implementation | Speed | RAM | Notes |
|---|---|---|---|
| Ollama | ~3.8 tok/s | 5.2 GB | Easiest to use |
| llama.cpp Docker | ~3.8 tok/s | 3.5 GB | Lower RAM |
| llama.cpp Native | ~3.8 tok/s | 3.5 GB | Lowest RAM, full control |

**Takeaway:** Performance is nearly identical on CPU. The main difference is memory usage and ease of management.

### Model-Specific Performance

**MoE models perform better on CPU:**
- Qwen3-8B (dense): ~3.8 tok/s
- DeepSeek-Coder-V2 (MoE, 2.4B active): ~5.5 tok/s (+45% faster!)

---

## Managing the Server

### Check Server Status

```bash
# Health check
curl http://localhost:8080/health

# List loaded models
curl http://localhost:8080/v1/models

# Server stats
curl http://localhost:8080/props
```

### Stop the Server

```bash
# Find the process
ps aux | grep llama-server

# Kill it
pkill llama-server
```

### Logs

If running in background with `nohup`:
```bash
tail -f ~/llama-server.log
```

Look for:
- `model loaded` - Model successfully loaded
- `server is listening` - Server is ready
- `eval time` - Token generation performance metrics

---

## Running Multiple Models

You can run multiple llama-server instances on different ports:

```bash
# Qwen3 on port 8080
~/llama.cpp/build/bin/llama-server \
  -m /home/user/llms/Qwen3-8B-Q4_K_M.gguf \
  --port 8080 -t 6 &

# DeepSeek on port 8081
~/llama.cpp/build/bin/llama-server \
  -m /home/user/llms/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf \
  --port 8081 -t 6 &
```

**RAM usage:** Both models loaded = 3.5GB + 10GB = 13.5GB total.

---

## Systemd Service (Optional)

To run llama-server as a service that starts on boot:

```bash
sudo tee /etc/systemd/system/llama-server.service > /dev/null << 'EOF'
[Unit]
Description=llama.cpp server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user
ExecStart=/home/user/llama.cpp/build/bin/llama-server \
  -m /home/user/llms/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -t 6 \
  -c 2048 \
  --parallel 1 \
  -fa on
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable llama-server
sudo systemctl start llama-server
```

Check status:
```bash
sudo systemctl status llama-server
journalctl -u llama-server -f
```

---

## Troubleshooting

### Server won't start

**Check the logs:**
```bash
tail ~/llama-server.log
```

**Common issues:**
- Port already in use: `Address already in use`
  - Fix: Change port with `--port 8081`
- Model not found: `error loading model`
  - Fix: Check model path with `ls -lh /path/to/model.gguf`
- Out of memory: `failed to allocate`
  - Fix: Use smaller model or increase swap

### Slow performance

- Check thread count: Try 4, 6, 8 threads and benchmark
- Use MoE models: DeepSeek-Coder-V2 is 45% faster than dense models
- Lower quantization: Q4_K_M > Q6_K > Q8_0 (smaller = faster)
- Reduce context: `-c 2048` instead of `-c 4096`

### Connection refused

```bash
# Check if server is running
ps aux | grep llama-server

# Check if port is listening
ss -tlnp | grep 8080

# Test locally
curl http://localhost:8080/health
```

---

## Next Steps

- See [llama.cpp API Guide](llamacpp-api.md) for API usage and MarkdownKB integration
- See [Performance Comparison](ollama-remote-setup.md#recommended-models) for model recommendations
