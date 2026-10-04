"""上下文记忆模块。

维护多轮对话历史，使 Agent 具备上下文理解能力。
支持消息的添加、裁剪（限制 token 数）和导出。
"""

from __future__ import annotations

from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# 单条消息最大字符数（粗略估算，避免单条消息过大撑爆上下文）
_MAX_MSG_CHARS = 12000


class ConversationMemory:
    """对话记忆，存储多轮消息历史。"""

    def __init__(self, system_prompt: str = "", max_messages: int = 40):
        self._messages: List[BaseMessage] = []
        self.system_prompt = system_prompt
        self._max_messages = max_messages

    @property
    def messages(self) -> List[BaseMessage]:
        """返回对话历史消息列表（不含系统提示词，系统提示词由 Agent 框架管理）。"""
        return list(self._messages)

    def add_user(self, content: str) -> None:
        """添加用户消息。"""
        self._messages.append(HumanMessage(content=self._truncate(content)))
        self._trim()

    def add_ai(self, content: str) -> None:
        """添加 AI 消息。"""
        self._messages.append(AIMessage(content=self._truncate(content)))
        self._trim()

    def add_tool_message(self, message: BaseMessage) -> None:
        """添加工具消息（LangChain Agent 内部使用）。"""
        self._messages.append(message)
        self._trim()

    def clear(self) -> None:
        """清空对话历史。"""
        self._messages.clear()

    def history_summary(self) -> str:
        """返回对话历史的简要摘要（用于 CLI 显示）。"""
        user_count = sum(1 for m in self._messages if isinstance(m, HumanMessage))
        ai_count = sum(1 for m in self._messages if isinstance(m, AIMessage))
        return f"已进行 {user_count} 轮用户交互，{ai_count} 次 AI 回复"

    @staticmethod
    def _truncate(content: str) -> str:
        if len(content) > _MAX_MSG_CHARS:
            return content[:_MAX_MSG_CHARS] + "\n... [内容过长已截断]"
        return content

    def _trim(self) -> None:
        """保留最近的消息，避免历史过长。"""
        if len(self._messages) > self._max_messages:
            # 保留系统提示词 + 最近 max_messages 条
            self._messages = self._messages[-self._max_messages :]
