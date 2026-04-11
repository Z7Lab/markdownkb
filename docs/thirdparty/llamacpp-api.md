# llama.cpp OpenAI-Compatible API Guide

llama-server provides an OpenAI-compatible API, making it easy to integrate with existing tools and libraries. This guide covers the API endpoints and how to configure MarkdownKB to use llama.cpp.

---

## API Overview

llama-server implements the OpenAI Chat Completions API (`/v1/chat/completions`), allowing you to use any OpenAI-compatible client library.

**Key endpoints:**
- `/health` - Health check
- `/v1/models` - List available models
- `/v1/chat/completions` - Chat completions (main endpoint)
- `/props` - Server properties and stats

---

## Basic API Usage

### Health Check

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{"status":"ok"}
```

### List Models

```bash
curl http://localhost:8080/v1/models
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen3-8B-Q4_K_M.gguf",
      "object": "model",
      "created": 1770968787,
      "owned_by": "llamacpp"
    }
  ]
}
```

### Chat Completion

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [
      {"role": "user", "content": "Explain recursion in one sentence."}
    ],
    "max_tokens": 50,
    "temperature": 0.7,
    "stream": false
  }'
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1770968787,
  "model": "Qwen3-8B-Q4_K_M.gguf",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Recursion is when a function calls itself..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 45,
    "total_tokens": 57
  },
  "timings": {
    "prompt_ms": 500.2,
    "predicted_ms": 11234.5,
    "predicted_per_second": 4.01
  }
}
```

---

## API Parameters

### Request Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `model` | string | Model name (can be any string) | Required |
| `messages` | array | Chat messages | Required |
| `max_tokens` | integer | Maximum tokens to generate | `inf` |
| `temperature` | float | Randomness (0.0-2.0) | `0.8` |
| `top_p` | float | Nucleus sampling (0.0-1.0) | `0.95` |
| `top_k` | integer | Top-k sampling | `40` |
| `stream` | boolean | Stream responses | `false` |
| `stop` | array | Stop sequences | `[]` |
| `presence_penalty` | float | Presence penalty (-2.0 to 2.0) | `0.0` |
| `frequency_penalty` | float | Frequency penalty (-2.0 to 2.0) | `0.0` |

### Message Format

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is Python?"},
    {"role": "assistant", "content": "Python is a programming language."},
    {"role": "user", "content": "Tell me more."}
  ]
}
```

**Roles:**
- `system` - System instructions (optional)
- `user` - User messages
- `assistant` - AI responses (for conversation history)

---

## Streaming Responses

Enable streaming for real-time token generation:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [{"role": "user", "content": "Count to 10"}],
    "stream": true
  }'
```

**Response (Server-Sent Events):**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"1"}}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":", 2"}}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":", 3"}}]}

data: [DONE]
```

---

## Using with Python

### With OpenAI SDK

```python
from openai import OpenAI

# Point to llama-server
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # llama-server doesn't require auth
)

response = client.chat.completions.create(
    model="qwen3",
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a Python hello world."}
    ],
    max_tokens=100,
    temperature=0.7
)

print(response.choices[0].message.content)
```

### With Requests

```python
import requests

response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
        "model": "qwen3",
        "messages": [{"role": "user", "content": "Hello!"}],
        "max_tokens": 50
    }
)

data = response.json()
print(data["choices"][0]["message"]["content"])
```

---

## Configuring MarkdownKB to Use llama.cpp

MarkdownKB uses the `openai` Python SDK for any OpenAI-compatible endpoint.

### Option 1: Edit `config/settings.yaml`

```yaml
llm:
  providers:
    - name: llamacpp
      model: openai/qwen3        # "openai/" prefix routes through the openai SDK
      api_base: "http://localhost:8080/v1"
  active_provider: llamacpp
  temperature: 0.3
  max_tokens: 2048
```

### Option 2: Use Environment Variable

```bash
export OPENAI_API_BASE=http://localhost:8080/v1
export OPENAI_API_KEY=dummy
python -m app
```

### Option 3: Run Multiple Models

Run different models on different ports for different use cases:

```yaml
llm:
  providers:
    - name: general
      model: openai/qwen3
      api_base: "http://localhost:8080/v1"  # General queries

    - name: coding
      model: openai/deepseek
      api_base: "http://localhost:8081/v1"  # Code-specific queries

  active_provider: coding  # Use DeepSeek by default
```

---

## Performance Monitoring

### Built-in Timing Metrics

llama-server includes detailed timing information in responses:

```json
{
  "timings": {
    "prompt_ms": 746.67,              // Time to process prompt
    "prompt_per_token_ms": 43.92,     // Prompt ms per token
    "prompt_per_second": 22.77,       // Prompt tokens/sec
    "predicted_ms": 7867.86,          // Time to generate tokens
    "predicted_per_token_ms": 262.26, // Generation ms per token
    "predicted_per_second": 3.81      // Generation tokens/sec ⭐
  }
}
```

**Key metric:** `predicted_per_second` = generation speed in tokens/sec.

### Quick Performance Test

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "messages": [{"role": "user", "content": "Count from 1 to 10."}],
    "max_tokens": 30
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Speed: {d[\"timings\"][\"predicted_per_second\"]:.2f} tok/s')
print(f'Tokens: {d[\"usage\"][\"completion_tokens\"]}')
print(f'Time: {d[\"timings\"][\"predicted_ms\"]/1000:.2f}s')
"
```

---

## Advanced Features

### System Prompts

Set a system prompt for all requests:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [
      {"role": "system", "content": "You are an expert Python developer. Answer concisely."},
      {"role": "user", "content": "How do I reverse a list?"}
    ]
  }'
```

### Stop Sequences

Stop generation at specific tokens:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [{"role": "user", "content": "List 5 fruits:"}],
    "stop": ["\n6.", "Done"],
    "max_tokens": 100
  }'
```

### Temperature Control

- `0.0` - Deterministic (always same output)
- `0.3-0.5` - Focused, consistent (good for RAG)
- `0.7-0.9` - Balanced creativity
- `1.0+` - Very creative/random

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3",
    "messages": [{"role": "user", "content": "Write a creative story."}],
    "temperature": 1.2,
    "top_p": 0.9
  }'
```

---

## Differences from Ollama API

llama.cpp uses the OpenAI API format, which differs from Ollama's native API:

| Feature | Ollama | llama.cpp |
|---------|--------|-----------|
| API format | Custom | OpenAI-compatible |
| Endpoint | `/api/generate` | `/v1/chat/completions` |
| Message format | `{"prompt": "..."}` | `{"messages": [...]}` |
| Model management | `ollama pull/list/rm` | Manual GGUF files |
| Streaming | `stream: true` | `stream: true` (SSE format) |
| Auth | None | None (but supports header passthrough) |

### Migration Example

**Ollama:**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Hello",
  "stream": false
}'
```

**llama.cpp:**
```bash
curl http://localhost:8080/v1/chat/completions -d '{
  "model": "qwen3",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false
}'
```

---

## Troubleshooting

### Empty responses

**Problem:** Response has empty `content`.

**Cause:** Model hasn't finished generating or wrong template.

**Fix:**
- Increase `max_tokens`
- Check model supports chat format
- Try without system message

### Slow first request

**Problem:** First request takes 10+ seconds.

**Cause:** Model loading into RAM.

**Fix:** This is normal. Subsequent requests are fast.

### "Model not found" error

**Problem:** API returns 404 for model.

**Cause:** llama-server accepts any model name - this shouldn't happen.

**Fix:** Check server logs with `tail ~/llama-server.log`

### Connection refused

**Problem:** `curl: (7) Failed to connect`

**Cause:** Server not running or wrong port.

**Fix:**
```bash
# Check if server is running
ps aux | grep llama-server

# Check port
ss -tlnp | grep 8080

# Start server
~/llama.cpp/build/bin/llama-server -m model.gguf --port 8080
```

---

## Best Practices

1. **Use streaming for interactive applications** - Better UX with real-time responses
2. **Set `max_tokens`** - Prevents runaway generation
3. **Use system prompts** - Guide model behavior consistently
4. **Monitor `timings`** - Track performance degradation
5. **Lower temperature for RAG** - Use 0.3-0.5 for fact-based Q&A
6. **Use stop sequences** - Control output format precisely

---

## Using MarkdownKB with llama.cpp

There are several ways to combine MarkdownKB's knowledge base with llama.cpp, depending on how you work.

### Option 1: Point MarkdownKB at your llama.cpp (recommended)

The simplest path. MarkdownKB handles all retrieval and uses your llama.cpp instance as the LLM. You get RAG chat, search, and the full web UI — without changing how llama.cpp runs.

In `config/settings.yaml`:

```yaml
llm:
  providers:
    - name: llamacpp
      model: openai/your-model-name
      api_base: http://localhost:8080/v1
  active_provider: llamacpp
```

Then use MarkdownKB normally — web UI, CLI, or MCP — and your llama.cpp does the generation.

### Option 2: Use the MarkdownKB CLI alongside llama.cpp

If you're scripting with llama.cpp's API directly and want to inject relevant knowledge, use the CLI to retrieve context first:

```bash
# Retrieve relevant chunks as JSON
CONTEXT=$(markdownkb search "your question here" --json | jq -r '.results[].content' | head -c 4000)

# Feed into llama.cpp with your own prompt
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"your-model\",
    \"messages\": [
      {\"role\": \"system\", \"content\": \"Answer using this context:\n$CONTEXT\"},
      {\"role\": \"user\", \"content\": \"your question here\"}
    ]
  }"
```

This is the manual RAG pipeline — you own the prompt, MarkdownKB owns the retrieval. Useful when you need full control over how context is injected.

### Option 3: Use the MarkdownKB REST API from your own code

MarkdownKB exposes `/api/search` and `/api/chat` endpoints you can call from any language. If you want to build your own application that uses llama.cpp for some things and MarkdownKB's knowledge for others, call the MarkdownKB API for retrieval and your llama.cpp endpoint for generation — mixing them however you need.

See [API Reference](../reference/api.md) and [CLI](../reference/cli.md).

### What about the llama.cpp browser UI and MCP?

llama-server's built-in web UI supports MCP — you can add MarkdownKB as an MCP server there. However, this only works **inside that browser session**. The MCP tools run in the browser: it fetches tool definitions from MarkdownKB, injects them into the prompt as text, and intercepts model responses to execute calls.

This means:
- **llama.cpp browser chat** — MCP works, MarkdownKB tools available
- **Direct API calls** (`/v1/chat/completions`) — no MCP, nothing intercepts tool calls
- **Your own scripts** — use Option 2 or 3 above instead

---

## Additional Resources

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat) - Full API specification
- [llama.cpp Documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
- [MarkdownKB Configuration Guide](../reference/configuration.md)
