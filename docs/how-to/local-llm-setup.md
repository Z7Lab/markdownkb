# Local LLM Setup

Step-by-step guide for setting up a local LLM with Ollama. After this, mdkb can chat and search using a model running entirely on your machine — no cloud API, no data leaving your network.

## Install Ollama

### macOS

```bash
brew install ollama
```

Or download from https://ollama.com/download/mac

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

Download from https://ollama.com/download/windows and run the installer.

## Pull a Model

Ollama needs at least one model downloaded. For general knowledge-base chat:

```bash
# Good default — fast, multilingual, 5GB
ollama pull qwen3:8b

# Alternative — Meta's general-purpose model
ollama pull llama3.1:8b

# Lightweight — runs well on low-memory machines
ollama pull gemma3:4b
```

**Which model to choose:**

| Model | Size | Best for |
|-------|------|----------|
| `qwen3:8b` | 5 GB | General purpose, multilingual, good reasoning |
| `llama3.1:8b` | 5 GB | English-focused, strong instruction following |
| `gemma3:4b` | 3 GB | Low memory machines, fast responses |
| `gemma4:e4b` | 10 GB | Latest generation, best quality at 4B active params |

You can also pull models from the mdkb UI — go to Settings > Chat Model, select Ollama, and use the "Pull Model" section with suggested models.

## Configure mdkb

### From the UI

1. Go to Settings > Chat Model
2. Select **ollama** from the Provider dropdown
3. Set API Base to `http://localhost:11434`
4. Click Refresh — your pulled models appear in the dropdown
5. Select a model and click Save

### From settings.yaml

```yaml
llm:
  providers:
    - name: ollama
      model: ollama/qwen3:8b
      api_base: http://localhost:11434
  active_provider: ollama
  temperature: 0.3
  max_tokens: 2048
```

### Docker users

Ollama runs on the host, not inside the container. Use `host.docker.internal` as the hostname:

```yaml
llm:
  providers:
    - name: ollama
      model: ollama/qwen3:8b
      api_base: http://host.docker.internal:11434
```

## Verify

In mdkb Settings > Chat Model, click "Ping Model". You should see a success message with response time.

Or use the Test Prompt section to send a quick message and confirm the model responds.

## Embedding Models

Embeddings are separate from the chat model. By default, mdkb uses a local ONNX model for embeddings (no Ollama needed). If you want to use Ollama for embeddings too (e.g. to offload to a faster machine), see [Embedding Models](embedding-models.md#remote-embeddings).

## Alternatives to Ollama

mdkb works with any OpenAI-compatible API. Other local options:

- **[llama.cpp](../thirdparty/llamacpp-setup.md)** — lower memory than Ollama, native CPU optimizations, full control. Build from source and run `llama-server`.
- **[LM Studio](https://lmstudio.ai/)** — GUI desktop app, download models from a catalog, one-click local server on port 1234.
- **[vLLM](https://docs.vllm.ai/)** — production-grade GPU-optimized serving with high throughput. Best for dedicated GPU machines.

To connect any of these, go to Settings > Chat Model, select **Custom (OpenAI-compatible)**, set the API base URL (e.g. `http://localhost:1234/v1` for LM Studio), and click Refresh.

## Remote LLM (Different Machine)

If the LLM server runs on a different machine on your network, see [Remote LLM Setup](remote-llm-setup.md) for network configuration and Docker setup.

## Troubleshooting

**"Cannot connect to Ollama"**
- Check Ollama is running: `ollama list` should show your models
- Check the port: `curl http://localhost:11434/api/tags` should return JSON
- Docker users: use `host.docker.internal` not `localhost`

**"Model not found"**
- Pull the model first: `ollama pull <model-name>`
- Check the model name matches exactly (including tag, e.g. `qwen3:8b` not just `qwen3`)

**Slow responses**
- Expected on CPU — 3-8 tokens/second depending on model and hardware
- Try a smaller model: `gemma3:4b` is faster than `qwen3:8b`
- Lower `max_tokens` in settings to reduce generation time
- Consider running Ollama on a machine with more CPU cores or a GPU
