# LLM Performance Benchmarking Guide

This guide explains how to measure and compare tokens-per-second (tok/s) performance for different LLM implementations: Ollama, llama.cpp Docker, and llama.cpp native builds.

---

## Why Benchmark?

**Tokens per second (tok/s)** is the primary performance metric for LLM inference:
- Higher tok/s = faster responses
- Typical CPU inference: 3-8 tok/s for 8B models
- GPU inference: 40-100+ tok/s
- MoE models can be 40-50% faster on CPU than dense models

**What affects performance:**
- CPU architecture (Ice Lake > Skylake)
- Thread count and hyperthreading
- Model size and quantization (Q4 > Q6 > Q8)
- Model architecture (MoE > dense for CPU)
- Flash attention and KV cache settings

---

## Benchmarking Ollama

### Basic Test

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Count from 1 to 10.",
  "stream": false,
  "options": {"num_predict": 30}
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
prompt_tps = d['prompt_eval_count'] / (d['prompt_eval_duration'] / 1e9)
print(f'Prompt processing: {prompt_tps:.2f} tok/s ({d[\"prompt_eval_count\"]} tokens)')
print(f'Token generation: {tps:.2f} tok/s ({d[\"eval_count\"]} tokens)')
print(f'Total time: {(d[\"prompt_eval_duration\"] + d[\"eval_duration\"]) / 1e9:.2f}s')
"
```

**Sample output:**
```
Prompt processing: 24.17 tok/s (6 tokens)
Token generation: 3.85 tok/s (30 tokens)
Total time: 8.03s
```

### Understanding Ollama Response

```json
{
  "model": "qwen3:8b",
  "response": "1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
  "prompt_eval_count": 6,
  "prompt_eval_duration": 248392000,
  "eval_count": 30,
  "eval_duration": 7790024000
}
```

**Key fields:**
- `eval_count` - Tokens generated
- `eval_duration` - Generation time in nanoseconds
- `prompt_eval_count` - Prompt tokens processed
- `prompt_eval_duration` - Prompt processing time in nanoseconds

**Calculate tok/s:**
```python
tokens_per_second = eval_count / (eval_duration / 1e9)
# Example: 30 / (7.79) = 3.85 tok/s
```

---

## Benchmarking llama.cpp

### Native or Docker Build

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [{"role": "user", "content": "Count from 1 to 10."}],
    "max_tokens": 30,
    "stream": false
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['timings']['predicted_per_second']
tokens = d['usage']['completion_tokens']
time = d['timings']['predicted_ms'] / 1000
print(f'Token generation: {tps:.2f} tok/s ({tokens} tokens in {time:.2f}s)')
"
```

**Sample output:**
```
Token generation: 3.81 tok/s (30 tokens in 7.87s)
```

### Understanding llama.cpp Response

```json
{
  "choices": [
    {
      "message": {"role": "assistant", "content": "1, 2, 3..."},
      "finish_reason": "length"
    }
  ],
  "usage": {
    "prompt_tokens": 17,
    "completion_tokens": 30,
    "total_tokens": 47
  },
  "timings": {
    "prompt_ms": 703.49,
    "prompt_per_token_ms": 41.38,
    "prompt_per_second": 24.17,
    "predicted_ms": 7790.02,
    "predicted_per_token_ms": 259.67,
    "predicted_per_second": 3.85
  }
}
```

**Key field:**
- `timings.predicted_per_second` - Direct tok/s measurement ⭐

---

## Comparative Benchmarking Script

Test multiple implementations at once:

```bash
#!/bin/bash
# save as benchmark.sh

echo "=== LLM PERFORMANCE BENCHMARK ==="
echo "Test: Generate 50 tokens"
echo ""

# Test Ollama
echo "1. Ollama (qwen3:8b):"
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Write a short poem about coding.",
  "stream": false,
  "options": {"num_predict": 50}
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
print(f'   {tps:.2f} tok/s')
"

# Test llama.cpp
echo "2. llama.cpp native (Qwen3-8B):"
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [{"role": "user", "content": "Write a short poem about coding."}],
    "max_tokens": 50,
    "stream": false
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'   {d[\"timings\"][\"predicted_per_second\"]:.2f} tok/s')
"

# Test DeepSeek if available
echo "3. Ollama (deepseek-coder-v2):"
curl -s http://localhost:11434/api/generate -d '{
  "model": "deepseek-coder-v2:latest",
  "prompt": "Write a short poem about coding.",
  "stream": false,
  "options": {"num_predict": 50}
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
print(f'   {tps:.2f} tok/s')
"
```

**Run it:**
```bash
chmod +x benchmark.sh
./benchmark.sh
```

**Sample output:**
```
=== LLM PERFORMANCE BENCHMARK ===
Test: Generate 50 tokens

1. Ollama (qwen3:8b):
   3.78 tok/s
2. llama.cpp native (Qwen3-8B):
   3.81 tok/s
3. Ollama (deepseek-coder-v2):
   5.50 tok/s
```

---

## Model-Specific Benchmarks

### Testing Different Quantization Levels

Compare Q4, Q6, Q8:

```bash
# Q4_K_M (fastest, smallest)
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Test",
  "options": {"num_predict": 50}
}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'Q4_K_M: {d[\"eval_count\"]/(d[\"eval_duration\"]/1e9):.2f} tok/s')"

# Q8_0 (slower, higher quality)
# Note: You'd need to create and load a Q8_0 version of the model
```

### Testing MoE vs Dense Models

```bash
echo "Dense model (Qwen3-8B, 8B params):"
# Run benchmark...

echo "MoE model (DeepSeek-Coder-V2, 2.4B active):"
# Run benchmark...
```

**Expected results on CPU:**
- Dense 8B: ~3.8 tok/s
- MoE 2.4B active: ~5.5 tok/s (+45%)

---

## Thread Count Optimization

Test different thread counts to find optimal setting:

```bash
#!/bin/bash
# Test thread counts 4, 6, 8

for threads in 4 6 8; do
  echo "Testing $threads threads..."

  # Stop existing server
  pkill llama-server
  sleep 1

  # Start with specific thread count
  ~/llama.cpp/build/bin/llama-server \
    -m ~/llms/Qwen3-8B-Q4_K_M.gguf \
    --port 8080 -t $threads \
    > /dev/null 2>&1 &

  sleep 5

  # Benchmark
  curl -s http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "test",
      "messages": [{"role": "user", "content": "Count to 20."}],
      "max_tokens": 40
    }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'$threads threads: {d[\"timings\"][\"predicted_per_second\"]:.2f} tok/s')
"
done

pkill llama-server
```

**Sample results:**
```
Testing 4 threads...
4 threads: 3.85 tok/s
Testing 6 threads...
6 threads: 3.84 tok/s
Testing 8 threads...
8 threads: 2.44 tok/s
```

**Conclusion:** 6 threads optimal for this 4-core/8-thread CPU.

---

## Measuring Prompt Processing Speed

Prompt processing is typically 5-10x faster than generation:

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "messages": [{"role": "user", "content": "'"$(cat large_document.txt)"'"}],
    "max_tokens": 10
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
prompt_tps = d['timings']['prompt_per_second']
print(f'Prompt processing: {prompt_tps:.2f} tok/s')
print(f'Prompt tokens: {d[\"usage\"][\"prompt_tokens\"]}')
"
```

---

## Real-World Benchmarks

### Short Q&A (Typical RAG Use Case)

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "What is Python? Answer in 20 words.",
  "stream": false,
  "options": {"num_predict": 30}
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
total_time = (d['prompt_eval_duration'] + d['eval_duration']) / 1e9
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
print(f'Response time: {total_time:.2f}s')
print(f'Generation speed: {tps:.2f} tok/s')
"
```

### Long-Form Generation

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Write a detailed explanation of recursion with examples.",
  "stream": false,
  "options": {"num_predict": 200}
}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
tps = d['eval_count'] / (d['eval_duration'] / 1e9)
total_time = (d['prompt_eval_duration'] + d['eval_duration']) / 1e9
print(f'Tokens generated: {d[\"eval_count\"]}')
print(f'Total time: {total_time:.2f}s')
print(f'Speed: {tps:.2f} tok/s')
"
```

---

## Benchmark Results Reference

### Intel i7-1165G7 (4-core, 8-thread, Ice Lake)

| Model | Implementation | Quantization | Speed | RAM |
|-------|---------------|--------------|-------|-----|
| Qwen3-8B | Ollama | Q4_K_M | 3.78 tok/s | 5.2 GB |
| Qwen3-8B | llama.cpp Docker | Q4_K_M | 3.85 tok/s | 3.5 GB |
| Qwen3-8B | llama.cpp Native | Q4_K_M | 3.81 tok/s | 3.5 GB |
| DeepSeek-Coder-V2 | Ollama | Q4_K_M | 5.50 tok/s | 10 GB |

**Key findings:**
- Ollama vs llama.cpp: Virtually identical performance (~3.8 tok/s)
- MoE models: 45% faster than dense models on CPU
- Native builds: No performance gain over Docker on this CPU
- Memory: llama.cpp uses ~30% less RAM than Ollama

---

## Interpreting Results

### What's Good Performance?

**CPU-only inference (Q4_K_M):**
- 3-6 tok/s: Normal for 7-8B dense models
- 5-8 tok/s: Normal for MoE models (2-3B active)
- 8-12 tok/s: Good (high-end desktop CPU or small model)
- 15+ tok/s: Excellent (likely ARM CPU or lighter quantization)

**GPU inference:**
- 40-60 tok/s: Budget GPU (GTX 1660, etc.)
- 60-100 tok/s: Mid-range GPU (RTX 3060, etc.)
- 100+ tok/s: High-end GPU (RTX 4090, A100, etc.)

### Performance Expectations by Hardware

| Hardware | 8B Model (Q4) | Expected Speed |
|----------|---------------|----------------|
| Laptop i7 (4-core) | Qwen3-8B | 3-4 tok/s |
| Desktop i7 (8-core) | Qwen3-8B | 5-7 tok/s |
| Apple M1/M2 | Qwen3-8B | 8-12 tok/s |
| NVIDIA RTX 3060 | Qwen3-8B | 50-70 tok/s |
| Apple M3 Max | Qwen3-8B | 15-25 tok/s |

---

## Common Performance Issues

### Slower than expected

**Possible causes:**
1. Thermal throttling (laptop CPUs)
2. Wrong thread count (too many or too few)
3. Swap being used (insufficient RAM)
4. Background processes consuming CPU

**Solutions:**
```bash
# Check CPU throttling
watch -n 1 'cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq'

# Check memory usage
free -h

# Check CPU usage
htop

# Reduce thread count
# Try -t 4 instead of -t 8
```

### Inconsistent performance

**Cause:** First token is always slower (model loading/warmup).

**Solution:** Ignore first request in benchmarks, or keep server running.

### Prompt processing slow

**Cause:** Large context, inefficient tokenization.

**Solution:**
- Use smaller context window (`-c 2048` instead of `-c 4096`)
- Enable flash attention (`-fa on`)
- Reduce prompt size

---

## Automated Benchmark Suite

Complete benchmark script:

```bash
#!/bin/bash
# comprehensive-benchmark.sh

MODELS=("qwen3:8b" "deepseek-coder-v2:latest")
PROMPTS=(
  "Count from 1 to 10."
  "Write a Python hello world."
  "Explain machine learning in simple terms."
)

echo "=== LLM Performance Benchmark Suite ==="
echo "Date: $(date)"
echo "CPU: $(lscpu | grep 'Model name' | cut -d: -f2 | xargs)"
echo ""

for model in "${MODELS[@]}"; do
  echo "Testing: $model"
  for i in "${!PROMPTS[@]}"; do
    prompt="${PROMPTS[$i]}"
    result=$(curl -s http://localhost:11434/api/generate -d "{
      \"model\": \"$model\",
      \"prompt\": \"$prompt\",
      \"stream\": false,
      \"options\": {\"num_predict\": 50}
    }" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tps = d['eval_count'] / (d['eval_duration'] / 1e9)
    print(f'{tps:.2f}')
except:
    print('ERROR')
")
    echo "  Prompt $((i+1)): $result tok/s"
  done
  echo ""
done
```

---

## Conclusion

**Key takeaways:**
1. Tokens/sec is the primary LLM performance metric
2. Ollama and llama.cpp perform identically on CPU (~3.8 tok/s for 8B Q4 models)
3. MoE models are significantly faster on CPU than dense models
4. Thread count optimization matters (usually cores - 2)
5. First request is always slower (model loading)

**For mdkb:**
- Use DeepSeek-Coder-V2 for 45% faster code-related queries
- Ollama is fine for convenience (same speed as llama.cpp on CPU)
- ~4 tok/s is expected on laptop CPUs for Q4_K_M 8B models
