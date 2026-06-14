# Hung-Yi Inspired AI Tutor VTuber MVP

This is an unofficial AI teaching assistant. It is inspired by Professor Hung-Yi Lee's teaching style. It is not Professor Hung-Yi Lee, not official, and not endorsed by him.

這不是李宏毅老師本人、不是官方頻道、不是授權代理，只是受公開教學風格啟發的 AI 教學助理實驗。

## Purpose

This MVP connects Open-LLM-VTuber to a local OpenAI-compatible RAG proxy. Open-LLM-VTuber calls the proxy as if it were a normal OpenAI-compatible model. The proxy retrieves relevant context from `hung-yi-lee-skill`, adds a safe teaching prompt, then forwards the request to your chosen upstream LLM.

## Architecture

```text
User / Open-LLM-VTuber
    -> OpenAI-compatible API
hungyi-rag-proxy
    -> search / graph query
hung-yi-lee-skill
    -> retrieved context
LLM backend
    -> answer
Open-LLM-VTuber Live2D + TTS
```

## Current Tool Status

On this machine, `git` and `py` were found, but `py -3` reported no usable Python runtime. `uv`, `ffmpeg`, `winget`, and optional `ollama` were not found on PATH during setup.

A usable Python 3 runtime is required for the proxy and `hung-yi-lee-skill`. `uv` is needed by Open-LLM-VTuber startup. `ffmpeg` is commonly needed for audio/video workflows. `ollama` is optional because you can use any OpenAI-compatible API instead.

## Files

Expected layout:

```text
E:\VTUBER\hong-yi
|- Open-LLM-VTuber\
|- hung-yi-lee-skill\
|- hungyi-rag-proxy\
|  |- server.py
|  |- requirements.txt
|  |- .env.example
|  |- .env
|  |- README_MVP.md
|  |- prompts\
|  |  \- hungyi_tutor_system_prompt.md
|  |- scripts\
|  |  |- setup_all.ps1
|  |  |- run_proxy.ps1
|  |  |- run_vtuber.ps1
|  |  |- smoke_test_proxy.ps1
|  |  \- configure_vtuber_openai_proxy.ps1
|  \- tests\
|     \- test_proxy_smoke.py
\- obs-assets\
   |- README_OBS.md
   \- overlay_disclaimer.html
```

## Install

From PowerShell:

```powershell
cd E:\VTUBER\hong-yi\hungyi-rag-proxy
.\scripts\setup_all.ps1
```

The script:

- checks the target folders
- creates `hungyi-rag-proxy\.venv`
- installs proxy requirements
- copies `.env.example` to `.env` if `.env` does not exist
- leaves existing `.env` untouched

Open-LLM-VTuber also requires `uv`. After installing `uv`, run:

```powershell
cd E:\VTUBER\hong-yi\Open-LLM-VTuber
uv sync
```

## Configure Open-LLM-VTuber

The helper script creates `conf.yaml` from `config_templates\conf.ZH.default.yaml` if needed, backs it up, and points the LLM provider at the proxy:

```powershell
cd E:\VTUBER\hong-yi\hungyi-rag-proxy
.\scripts\configure_vtuber_openai_proxy.ps1
```

Target settings:

```yaml
llm_provider: 'openai_compatible_llm'
openai_compatible_llm:
  base_url: 'http://127.0.0.1:8765/v1'
  llm_api_key: 'not-needed'
  model: 'hungyi-rag-proxy'
```

The script also replaces the persona prompt with a safe unofficial AI tutor prompt.

## Upstream Mode A: Ollama Local Model

Install and start Ollama separately, then pull or run a model:

```powershell
ollama list
ollama run qwen2.5:latest
```

Set `hungyi-rag-proxy\.env`:

```env
UPSTREAM_MODE=ollama_native
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:latest
```

## Upstream Mode B: OpenAI-Compatible API

Use this for OpenAI-compatible local servers, hosted gateways, or Ollama's OpenAI-compatible endpoint.

Set `hungyi-rag-proxy\.env`:

```env
UPSTREAM_MODE=openai_compatible
UPSTREAM_BASE_URL=http://127.0.0.1:11434/v1
UPSTREAM_API_KEY=not-needed
UPSTREAM_MODEL=qwen2.5:latest
```

Do not hard-code API keys in `server.py`. Put them only in `.env`.

## Startup Order

1. Start the upstream LLM first, such as Ollama or your OpenAI-compatible API server.
2. Start the RAG proxy:

```powershell
cd E:\VTUBER\hong-yi\hungyi-rag-proxy
.\scripts\run_proxy.ps1
```

3. Start Open-LLM-VTuber:

```powershell
cd E:\VTUBER\hong-yi\Open-LLM-VTuber
..\hungyi-rag-proxy\scripts\run_vtuber.ps1
```

4. Open:

```text
http://localhost:12393
```

## Smoke Test

With the proxy running:

```powershell
cd E:\VTUBER\hong-yi\hungyi-rag-proxy
.\scripts\smoke_test_proxy.ps1
```

The smoke test calls:

- `GET http://127.0.0.1:8765/health`
- `POST http://127.0.0.1:8765/v1/chat/completions`

If the upstream LLM is not configured or not running, the proxy returns a clear assistant message with checks for Ollama, model name, API key, and base URL instead of a Python traceback.

## RAG Backend

The proxy first tries:

```powershell
python scripts\hungyi_kb.py search "attention" --limit 3
python scripts\hungyi_kb.py graph query "Transformer"
```

If the CLI is unavailable or errors, the proxy falls back to keyword search over markdown, text, and JSON files under:

- `wiki`
- `outputs`
- `references`
- `raw`

The `/health` endpoint reports the configured backend. Actual chat calls use CLI results when the CLI succeeds and fallback search otherwise.

## OBS

See `E:\VTUBER\hong-yi\obs-assets\README_OBS.md`.

Basic recommendation:

- Use OBS Window Capture for Open-LLM-VTuber or Chrome.
- Add visible text: `Unofficial AI Tutor | Inspired by public ML teaching style | Not official`.
- Do not use Professor Hung-Yi Lee's photo.
- Do not use cloned voice.
- Do not make the stream title look official.

## Safety And Copyright

This project must not impersonate Professor Hung-Yi Lee. It must not use his portrait, cloned voice, official identity, or misleading branding. User-visible material should make the unofficial status clear:

- This is an unofficial AI teaching assistant.
- It is inspired by Professor Hung-Yi Lee's teaching style.
- It is not Professor Hung-Yi Lee, not official, and not endorsed by him.

## Common Errors

`uv` does not exist:
Install `uv`, then run `uv sync` inside `Open-LLM-VTuber`.

`ffmpeg` does not exist:
Install `ffmpeg` and ensure it is on PATH before audio/video workflows.

`conf.yaml` does not exist:
Run `.\scripts\configure_vtuber_openai_proxy.ps1`; it can copy `config_templates\conf.ZH.default.yaml`.

Open-LLM-VTuber cannot find the model:
Confirm `conf.yaml` uses `openai_compatible_llm`, `base_url` is `http://127.0.0.1:8765/v1`, and `model` is `hungyi-rag-proxy`.

Ollama is not running:
Start Ollama and run `ollama run qwen2.5:latest`, or switch `.env` to a hosted OpenAI-compatible API.

Model name mismatch:
Make sure `.env` model names match the actual upstream model. For the proxy model exposed to Open-LLM-VTuber, use `hungyi-rag-proxy`.

Proxy prevents localhost connection:
Bypass system HTTP proxy for `127.0.0.1` and `localhost`.

Windows Chinese path issue:
Keep this project in `E:\VTUBER\hong-yi` or another ASCII-only path.
