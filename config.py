"""配置管理模块。

从环境变量或 .env 文件加载 LLM 与 Agent 的运行配置。
支持所有 OpenAI 兼容接口的服务商（OpenAI / DeepSeek / 通义千问 / Kimi / 智谱等）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent

# 自动加载 .env 文件（如果存在）
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class LLMConfig:
    """LLM 调用相关配置。"""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "未检测到 LLM_API_KEY 环境变量。\n"
                "请复制 .env.example 为 .env 并填入你的 API Key，"
                "或通过环境变量 LLM_API_KEY 提供。"
            )
        return cls(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        )


@dataclass
class AgentConfig:
    """Agent 运行相关配置。"""

    max_iterations: int = 10
    code_exec_timeout: int = 10

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
            code_exec_timeout=int(os.getenv("CODE_EXEC_TIMEOUT", "10")),
        )


@dataclass
class AppConfig:
    """应用总配置。"""

    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    agent: AgentConfig = field(default_factory=AgentConfig.from_env)

    @classmethod
    def load(cls) -> "AppConfig":
        return cls()
