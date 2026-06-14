from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODEL_ID = "hungyi-rag-proxy"
PROMPT_PATH = ROOT / "prompts" / "hungyi_tutor_system_prompt.md"


def env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


HUNGYI_SKILL_PATH = resolve_path(env("HUNGYI_SKILL_PATH", r"..\hung-yi-lee-skill"))
RAG_LIMIT = int(env("RAG_LIMIT", "6"))
RAG_TIMEOUT_SECONDS = int(env("RAG_TIMEOUT_SECONDS", "20"))
UPSTREAM_MODE = env("UPSTREAM_MODE", "openai_compatible")
UPSTREAM_BASE_URL = env("UPSTREAM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
UPSTREAM_API_KEY = env("UPSTREAM_API_KEY", "not-needed")
UPSTREAM_MODEL = env("UPSTREAM_MODEL", "qwen2.5:latest")
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = env("OLLAMA_MODEL", "qwen2.5:latest")
DEFAULT_TEMPERATURE = float(env("TEMPERATURE", "0.7"))
MAX_TOKENS = int(env("MAX_TOKENS", "1200"))


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    stream: bool = False
    max_tokens: Optional[int] = Field(default=None, alias="max_tokens")


app = FastAPI(title="Hung-Yi Inspired RAG Proxy", version="0.1.0")


def read_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def latest_user_query(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message_text(message.content)
    return message_text(messages[-1].content) if messages else ""


def candidate_python() -> str:
    skill_python = HUNGYI_SKILL_PATH / ".venv" / "Scripts" / "python.exe"
    if skill_python.exists():
        return str(skill_python)
    return sys.executable


def run_skill_cli(query: str) -> list[dict[str, str]]:
    script = HUNGYI_SKILL_PATH / "scripts" / "hungyi_kb.py"
    if not script.exists():
        return []

    cmd = [
        candidate_python(),
        str(script),
        "search",
        query,
        "--limit",
        str(RAG_LIMIT),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(HUNGYI_SKILL_PATH),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=RAG_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return []
    output = result.stdout.strip()
    if not output:
        return []
    return [{"source": "hung-yi-lee-skill CLI", "text": output[:6000]}]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def fallback_file_search(query: str) -> list[dict[str, str]]:
    roots = ["wiki", "outputs", "references", "raw"]
    suffixes = {".md", ".txt", ".json"}
    query_tokens = set(tokenize(query))
    scored: list[tuple[int, Path, str]] = []

    for folder in roots:
        root = HUNGYI_SKILL_PATH / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            haystack = text.lower()
            score = sum(haystack.count(token) for token in query_tokens if token)
            if score:
                snippet = text[:3000]
                scored.append((score, path, snippet))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "source": str(path.relative_to(HUNGYI_SKILL_PATH)),
            "text": snippet,
        }
        for _, path, snippet in scored[:RAG_LIMIT]
    ]


def retrieve_context(query: str) -> tuple[str, list[dict[str, str]]]:
    cli_results = run_skill_cli(query)
    if cli_results:
        return "hung-yi-lee-skill-cli", cli_results
    return "fallback-file-search", fallback_file_search(query)


def skill_cli_available() -> bool:
    script = HUNGYI_SKILL_PATH / "scripts" / "hungyi_kb.py"
    if not script.exists():
        return False
    try:
        result = subprocess.run(
            [candidate_python(), str(script), "search", "__healthcheck__", "--limit", "1"],
            cwd=str(HUNGYI_SKILL_PATH),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(RAG_TIMEOUT_SECONDS, 5),
        )
    except Exception:
        return False
    return result.returncode == 0


def context_block(results: list[dict[str, str]]) -> str:
    if not results:
        return "目前沒有找到相關 RAG 片段。請在回答中說明可能需要補齊資料。"
    blocks = []
    for index, item in enumerate(results, start=1):
        blocks.append(
            f"[{index}] Source: {item['source']}\n{item['text']}"
        )
    return "\n\n".join(blocks)


def build_messages(original: list[ChatMessage], query: str, results: list[dict[str, str]]) -> list[dict[str, str]]:
    prompt = read_system_prompt()
    rag = context_block(results)
    system = (
        f"{prompt}\n\n"
        "以下是可能相關的檢索資料。請優先根據資料回答；若資料不足，請明確說明。\n\n"
        f"{rag}\n\n"
        "身份安全提醒：This is an unofficial AI teaching assistant. "
        "It is inspired by Professor Hung-Yi Lee's teaching style. "
        "It is not Professor Hung-Yi Lee, not official, and not endorsed by him."
    )
    converted = [{"role": "system", "content": system}]
    for message in original:
        converted.append({"role": message.role, "content": message_text(message.content)})
    if not query:
        converted.append({"role": "user", "content": "請用繁體中文簡短說明你可以如何協助機器學習學習。"})
    return converted


def upstream_error_message(exc: Exception) -> str:
    return (
        "上游 LLM 呼叫失敗，所以 proxy 沒有產生模型回答。\n\n"
        "請檢查：\n"
        "1. 是否 Ollama 沒啟動。\n"
        "2. 是否模型不存在，請確認模型名稱與 .env 一致。\n"
        "3. 是否 API key 沒設或無效。\n"
        "4. 是否 base_url 錯誤。\n\n"
        f"目前設定：UPSTREAM_MODE={UPSTREAM_MODE}, "
        f"UPSTREAM_BASE_URL={UPSTREAM_BASE_URL}, OLLAMA_BASE_URL={OLLAMA_BASE_URL}, "
        f"UPSTREAM_MODEL={UPSTREAM_MODEL}, OLLAMA_MODEL={OLLAMA_MODEL}\n\n"
        f"技術訊息：{type(exc).__name__}: {exc}"
    )


async def call_openai_compatible(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
    payload = {
        "model": UPSTREAM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {UPSTREAM_API_KEY}"}
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{UPSTREAM_BASE_URL}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def call_ollama_native(messages: list[dict[str, str]], temperature: float) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    return data.get("message", {}).get("content", "")


async def complete_answer(request: ChatRequest) -> tuple[str, str]:
    query = latest_user_query(request.messages)
    backend, results = retrieve_context(query)
    messages = build_messages(request.messages, query, results)
    temperature = request.temperature if request.temperature is not None else DEFAULT_TEMPERATURE
    max_tokens = request.max_tokens or MAX_TOKENS
    try:
        if UPSTREAM_MODE == "ollama_native":
            answer = await call_ollama_native(messages, temperature)
        elif UPSTREAM_MODE == "openai_compatible":
            answer = await call_openai_compatible(messages, temperature, max_tokens)
        else:
            answer = f"不支援的 UPSTREAM_MODE：{UPSTREAM_MODE}。請設定為 openai_compatible 或 ollama_native。"
    except Exception as exc:
        answer = upstream_error_message(exc)
    return backend, answer


def chat_response(answer: str) -> dict[str, Any]:
    now = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": now,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def sse_chunks(answer: str):
    for index in range(0, len(answer), 80):
        chunk = answer[index : index + 80]
        payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": MODEL_ID,
            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    done = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/health")
def health() -> dict[str, str]:
    backend = "hung-yi-lee-skill-cli" if skill_cli_available() else "fallback-file-search"
    return {
        "status": "ok",
        "rag_backend": backend,
        "upstream_mode": UPSTREAM_MODE,
        "upstream_base_url": UPSTREAM_BASE_URL if UPSTREAM_MODE == "openai_compatible" else OLLAMA_BASE_URL,
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    _, answer = await complete_answer(request)
    if request.stream:
        return StreamingResponse(sse_chunks(answer), media_type="text/event-stream")
    return JSONResponse(chat_response(answer))
