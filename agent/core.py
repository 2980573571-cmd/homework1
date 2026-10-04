"""Agent 核心模块。

实现代码解释 Agent 的主循环：输入 → 推理 → 工具调用 → 输出。
基于 LangChain 的 create_agent 构建，支持上下文记忆与错误重试。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI

from config import AppConfig
from .memory import ConversationMemory
from .prompts import build_system_prompt
from .tools import get_tools


class CodeExplanationAgent:
    """代码解释 Agent。

    封装了 LLM、工具集、记忆系统和 Agent 主循环，提供代码解释、注释生成与代码问答能力。
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        self._llm = self._build_llm()
        self._tools = get_tools()
        self._memory = ConversationMemory(system_prompt=build_system_prompt())
        self._agent = create_agent(
            model=self._llm,
            tools=self._tools,
            system_prompt=build_system_prompt(),
        )

    def _build_llm(self) -> ChatOpenAI:
        """构建 LLM 实例，支持 OpenAI 兼容接口。"""
        return ChatOpenAI(
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
            model=self.config.llm.model,
            max_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
        )

    def chat(self, user_input: str) -> str:
        """处理用户输入，执行 Agent 循环并返回最终回复。

        Args:
            user_input: 用户的自然语言请求。

        Returns:
            Agent 的最终回复文本。
        """
        # 将用户输入加入记忆
        self._memory.add_user(user_input)

        # 构建输入状态（包含系统提示词 + 历史消息）
        input_state: Dict[str, Any] = {"messages": self._memory.messages}

        try:
            result = self._invoke_with_retry(input_state)
        except Exception as e:
            error_msg = f"Agent 执行出错: {self._format_error(e)}"
            self._memory.add_ai(error_msg)
            return error_msg

        # 从结果中提取 AI 的最终回复
        messages: List[BaseMessage] = result.get("messages", [])
        final_text = self._extract_final_text(messages)

        # 将 AI 回复加入记忆
        if final_text:
            self._memory.add_ai(final_text)
        return final_text

    def stream_chat(self, user_input: str):
        """流式处理用户输入，逐步产出事件，适合 Web / 终端实时展示。

        与 chat() 的区别在于：本方法通过 LangGraph 的流式接口逐步返回
        文本 token 与工具调用事件，而非等待完整回复后再一次性返回。

        Args:
            user_input: 用户的自然语言请求。

        Yields:
            dict: 事件对象，`type` 字段取值：
                - "tool": 调用了某个工具，附带 `name`
                - "text": 一段回复文本，附带 `text`
                - "error": 发生错误，附带 `text`（终止事件）
        """
        self._memory.add_user(user_input)
        input_state: Dict[str, Any] = {"messages": self._memory.messages}

        text_parts: List[str] = []
        seen_tools: set = set()

        try:
            for message, _metadata in self._agent.stream(
                input_state,
                config={"recursion_limit": self.config.agent.max_iterations * 3 + 5},
                stream_mode="messages",
            ):
                if isinstance(message, AIMessageChunk):
                    # 工具调用事件：流式分片中 name/id 仅出现在首个 chunk，
                    # 后续 chunk 只携带 args，故按稳定的 index 去重。
                    for tc in message.tool_call_chunks or []:
                        name = (tc.get("name") or "").strip()
                        if not name:
                            continue
                        key = tc.get("index")
                        if key is None:
                            key = tc.get("id") or name
                        if key not in seen_tools:
                            seen_tools.add(key)
                            yield {"type": "tool", "name": name}
                    # 文本 token
                    if message.content and isinstance(message.content, str):
                        text_parts.append(message.content)
                        yield {"type": "text", "text": message.content}
        except Exception as e:
            error_msg = f"Agent 执行出错: {self._format_error(e)}"
            self._memory.add_ai(error_msg)
            yield {"type": "error", "text": error_msg}
            return

        final_text = "".join(text_parts)
        if final_text:
            self._memory.add_ai(final_text)

    def _invoke_with_retry(self, input_state: Dict[str, Any]) -> Dict[str, Any]:
        """带重试机制的 Agent 调用。

        针对网络错误、速率限制等瞬时故障进行指数退避重试。
        """
        import time

        max_retries = 3
        base_delay = 1.0
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                return self._agent.invoke(
                    input_state,
                    config={"recursion_limit": self.config.agent.max_iterations * 3 + 5},
                )
            except Exception as e:
                last_exception = e
                if attempt < max_retries and self._is_retryable(e):
                    delay = base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
                    continue
                raise
        # 理论上不会到达这里
        raise last_exception  # type: ignore[misc]

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """判断异常是否可重试（网络/速率限制类错误）。"""
        msg = str(exc).lower()
        retry_keywords = [
            "rate limit",
            "429",
            "timeout",
            "timed out",
            "connection",
            "500",
            "502",
            "503",
            "504",
            "api error",
        ]
        return any(kw in msg for kw in retry_keywords)

    @staticmethod
    def _extract_final_text(messages: List[BaseMessage]) -> str:
        """从 Agent 输出的消息列表中提取最终 AI 回复。"""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                # content 可能是 str 或 list（包含 tool_calls 等）
                if isinstance(msg.content, str):
                    return msg.content
                # 若是结构化内容，提取 text 字段
                texts = [
                    part.get("text", "")
                    for part in msg.content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                return "\n".join(t for t in texts if t)
        return "(Agent 未生成有效回复)"

    @staticmethod
    def _format_error(exc: Exception) -> str:
        """将异常格式化为用户可读的错误信息。"""
        msg = str(exc)
        if "rate limit" in msg.lower() or "429" in msg:
            return "触发了 LLM 服务商的速率限制，请稍后重试或更换 API Key。"
        if "api key" in msg.lower() or "unauthorized" in msg.lower() or "401" in msg:
            return "API Key 无效或未授权，请检查 .env 中的 LLM_API_KEY 配置。"
        if "connection" in msg.lower() or "timeout" in msg.lower():
            return "网络连接失败，请检查网络或 LLM_BASE_URL 配置。"
        return msg

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    def clear_memory(self) -> None:
        """清空对话历史。"""
        self._memory.clear()
