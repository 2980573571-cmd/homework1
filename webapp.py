"""Code Explanation Agent - Streamlit 网页界面入口。

提供基于 Streamlit 的聊天式网页交互，支持流式输出、工具调用展示与上下文记忆。

用法:
    streamlit run webapp.py
"""

from __future__ import annotations

import streamlit as st

from agent import CodeExplanationAgent
from config import AppConfig

# 页面基本配置（须在其它 Streamlit 命令之前调用）
st.set_page_config(
    page_title="Code Explanation Agent",
    page_icon="🤖",
    layout="wide",
)

# 侧边栏示例问题
EXAMPLE_PROMPTS = [
    "解释 examples/sample_code.py 的逻辑",
    "为这段代码生成中文注释:\n\ndef add(a, b):\n    return a + b",
    "average_age 函数的时间复杂度是多少？",
    "搜索 add_user 方法在哪里被调用",
    "解释 agent/tools.py 的设计思路",
]


@st.cache_resource(show_spinner=False)
def _create_agent() -> CodeExplanationAgent:
    """创建并缓存 Agent 实例（LLM 客户端等资源应复用而非每次重建）。"""
    return CodeExplanationAgent(AppConfig.load())


def render_sidebar(agent: CodeExplanationAgent) -> None:
    """渲染侧边栏：配置信息、清空对话、示例问题。"""
    with st.sidebar:
        st.header("⚙️ 配置")
        st.write(f"**模型**：`{agent.config.llm.model}`")
        st.write(f"**接口**：`{agent.config.llm.base_url}`")

        st.divider()
        if st.button("🗑️ 清空对话"):
            agent.clear_memory()
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.header("💡 示例问题")
        for i, prompt in enumerate(EXAMPLE_PROMPTS):
            label = prompt.replace("\n", " ")[:40]
            if st.button(label, key=f"example_{i}"):
                st.session_state.pending_prompt = prompt


def main() -> None:
    """Streamlit 应用主流程。"""
    try:
        agent = _create_agent()
    except Exception as e:  # 配置缺失 / 依赖未安装等
        st.error(f"配置错误：{e}")
        st.info("请复制 .env.example 为 .env 并填入 API Key，然后重启应用。")
        st.stop()

    st.title("🤖 Code Explanation Agent")
    st.caption("解释代码逻辑 · 生成注释 · 代码问答 —— 支持工具调用与流式输出")

    # 展示层消息历史（与 Agent 内部记忆分离）
    if "messages" not in st.session_state:
        st.session_state.messages = []

    render_sidebar(agent)

    # 渲染历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 获取用户输入（聊天框 或 侧边栏示例按钮）
    prompt = st.chat_input("输入代码相关问题，例如「解释 examples/sample_code.py」...")
    if prompt is None:
        prompt = st.session_state.pop("pending_prompt", None)
    if not prompt:
        return

    # 用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent 流式回复
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        tool_caption = st.empty()

        full_text = ""
        tools_used: list[str] = []

        for event in agent.stream_chat(prompt):
            etype = event.get("type")
            if etype == "tool":
                name = event.get("name", "?")
                if name not in tools_used:
                    tools_used.append(name)
                tool_caption.caption("🔧 正在使用工具：" + "、".join(tools_used))
            elif etype == "text":
                full_text += event.get("text", "")
                text_placeholder.markdown(full_text)
            elif etype == "error":
                full_text = event.get("text", "（发生错误）")
                text_placeholder.markdown(full_text)

        if not full_text:
            full_text = "（Agent 未生成有效回复）"
            text_placeholder.markdown(full_text)

        if tools_used:
            tool_caption.caption("🔧 使用了工具：" + "、".join(tools_used))
        else:
            tool_caption.empty()

    st.session_state.messages.append({"role": "assistant", "content": full_text})


if __name__ == "__main__":
    main()
