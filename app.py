r"""Code Explanation Agent - 网页入口（自包含 Web 服务 + 对话框前端）。

基于 Starlette + uvicorn，复用现有 agent 包与 config 配置，
提供一个聊天对话框式的网页交互，支持流式输出、工具调用展示与上下文记忆。

用法:
    .venv\Scripts\python.exe app.py
    然后浏览器打开 http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import iterate_in_threadpool
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from agent import CodeExplanationAgent
from config import AppConfig

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

# 禁止缓冲，保证流式输出实时到达前端
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

# 懒加载的 Agent 单例（与 Streamlit 的 cache_resource 同理，复用 LLM 客户端等资源）
_agent: CodeExplanationAgent | None = None
_agent_error: Exception | None = None
_agent_lock = threading.Lock()


def get_agent() -> CodeExplanationAgent:
    """创建并复用 Agent 实例；配置缺失时抛出友好错误。"""
    global _agent, _agent_error
    if _agent is None and _agent_error is None:
        with _agent_lock:
            if _agent is None and _agent_error is None:
                try:
                    _agent = CodeExplanationAgent(AppConfig.load())
                except Exception as e:  # 缺少 API Key / 依赖未安装等
                    _agent_error = e
    if _agent_error is not None:
        raise _agent_error
    return _agent


def _sse(event: str, data: dict) -> str:
    """将事件序列化为 SSE（Server-Sent Events）文本帧。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _event_stream(agent: CodeExplanationAgent, message: str):
    """同步生成器：把 agent.stream_chat 的事件转换为 SSE 帧。

    `agent.stream_chat` 是阻塞的 LangGraph 流，交由 `iterate_in_threadpool`
    在后台线程池中迭代，避免阻塞 asyncio 事件循环。
    """
    try:
        for event in agent.stream_chat(message):
            etype = event.get("type")
            if etype == "tool":
                yield _sse("tool", {"name": event.get("name", "?")})
            elif etype == "text":
                yield _sse("text", {"text": event.get("text", "")})
            elif etype == "error":
                yield _sse("error", {"text": event.get("text", "（发生错误）")})
    except Exception as e:  # 兜底：任何未捕获异常都以 error 事件返回
        yield _sse("error", {"text": f"Agent 执行出错: {e}"})
    finally:
        yield _sse("done", {})


async def api_chat(request) -> StreamingResponse | JSONResponse:
    """POST /api/chat  —— 流式聊天接口，返回 SSE 事件流。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "无效的请求体"}, status_code=400)

    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "请输入内容"}, status_code=400)

    try:
        agent = get_agent()
    except Exception as e:
        return JSONResponse({"error": f"配置错误：{e}"}, status_code=500)

    return StreamingResponse(
        iterate_in_threadpool(_event_stream(agent, message)),
        media_type="text/event-stream",
        headers=_NO_CACHE_HEADERS,
    )


async def api_clear(request) -> JSONResponse:
    """POST /api/clear —— 清空对话历史。"""
    try:
        get_agent().clear_memory()
    except Exception:
        pass  # 即便 Agent 未初始化也返回成功，前端自行重置
    return JSONResponse({"ok": True})


async def api_config(request) -> JSONResponse:
    """GET /api/config —— 返回非敏感配置信息与就绪状态。"""
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    try:
        get_agent()
        ready = True
    except Exception:
        ready = False
    return JSONResponse({"model": model, "base_url": base_url, "ready": ready})


app = Starlette(
    routes=[
        Route("/api/chat", api_chat, methods=["POST"]),
        Route("/api/clear", api_clear, methods=["POST"]),
        Route("/api/config", api_config, methods=["GET"]),
        # 静态资源兜底："/" 自动返回 static/index.html
        Mount("/", app=StaticFiles(directory=str(STATIC_DIR), html=True), name="static"),
    ]
)


if __name__ == "__main__":
    # 直接传入 app 对象（而非 "app:app" 字符串），避免重复导入，
    # 且不依赖当前工作目录，在任何位置运行都能正确启动。
    uvicorn.run(app, host="127.0.0.1", port=8000)
