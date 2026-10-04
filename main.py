"""Code Explanation Agent - 命令行入口。

提供交互式 REPL 界面，支持多轮对话式代码解释、注释生成与代码问答。
使用 rich 库提供美观的终端输出。

用法:
    python main.py                      # 进入交互模式
    python main.py "解释 examples/sample_code.py"   # 单次查询模式
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status

from config import AppConfig
from agent import CodeExplanationAgent

console = Console()


def print_banner() -> None:
    """打印启动横幅。"""
    banner = r"""
  ____          _        ____                _
 / ___|___   __| | ___  |  _ \ _____   _____(_)_   _
| |   / _ \ / _` |/ _ \ | |_) / _ \ \ / / _ \ | | | |
| |__| (_) | (_| |  __/ |  _ <  __/\ V /  __/ | |_| |
 \____\___/ \__,_|\___| |_| \_\___| \_/ \___|_|\__,_|
"""
    console.print(Panel(banner, style="bold cyan", title="Code Explanation Agent"))
    console.print(
        "  输入你的代码相关问题（解释代码 / 生成注释 / 代码问答），\n"
        "  或输入 [bold green]help[/] 查看命令。\n"
        "  输入 [bold green]exit[/] / [bold green]quit[/] 退出。\n"
    )


def print_help() -> None:
    """打印帮助信息。"""
    help_text = """
**可用命令:**

| 命令 | 说明 |
|------|------|
| `help` | 显示本帮助信息 |
| `clear` | 清空对话历史 |
| `memory` | 显示当前对话状态 |
| `exit` / `quit` | 退出程序 |

**使用示例:**

- `解释 examples/sample_code.py 的逻辑`
- `为这段代码生成中文注释: <粘贴代码>`
- `average_age 函数的时间复杂度是多少？`
- `搜索 add_user 方法在哪里被调用`
- `解释 agent/tools.py 的设计思路`
"""
    console.print(Panel(Markdown(help_text), title="帮助", style="green"))


def stream_response(agent: CodeExplanationAgent, user_input: str) -> None:
    """调用 Agent 并展示结果。"""
    with Status("[bold yellow]Agent 正在思考...", console=console, spinner="dots"):
        response = agent.chat(user_input)
    console.print()
    console.print(Panel(Markdown(response), title="回答", style="bold blue", border_style="blue"))


def interactive_loop(agent: CodeExplanationAgent) -> None:
    """交互式对话循环。"""
    print_banner()
    while True:
        try:
            user_input = console.input("[bold green]你 >[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见！[/]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("exit", "quit"):
            console.print("[dim]再见！[/]")
            break
        if cmd == "help":
            print_help()
            continue
        if cmd == "clear":
            agent.clear_memory()
            console.print("[dim]对话历史已清空。[/]")
            continue
        if cmd == "memory":
            console.print(f"[dim]{agent.memory.history_summary()}[/]")
            continue

        try:
            stream_response(agent, user_input)
        except ValueError as e:
            console.print(f"[red]配置错误: {e}[/]")
            break
        except Exception as e:
            console.print(f"[red]发生错误: {e}[/]")


def single_query(agent: CodeExplanationAgent, query: str) -> None:
    """单次查询模式。"""
    try:
        stream_response(agent, query)
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]发生错误: {e}[/]")
        sys.exit(1)


def main() -> None:
    """主入口。"""
    # 加载配置并构建 Agent（两个模式共用同一套初始化逻辑）
    try:
        config = AppConfig.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/]")
        sys.exit(1)

    agent = CodeExplanationAgent(config)

    # 解析命令行参数：带参数走单次查询，否则进入交互模式
    if len(sys.argv) > 1:
        single_query(agent, " ".join(sys.argv[1:]))
    else:
        interactive_loop(agent)


if __name__ == "__main__":
    main()
