"""Agent 工具集。

提供文件读取、代码搜索、目录列表、代码执行等工具，供 Agent 在推理过程中调用。
所有工具均带有安全限制（路径白名单、超时、禁止危险操作）。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from langchain_core.tools import tool

# 允许访问的根目录（默认为当前工作目录）
_WORKSPACE_ROOT = Path.cwd().resolve()


def _resolve_path(path: str) -> Path:
    """将相对路径解析为绝对路径，并校验是否在工作区内。"""
    candidate = (Path(path).expanduser()).resolve()
    if not candidate.is_relative_to(_WORKSPACE_ROOT):
        raise PermissionError(
            f"路径 '{path}' 超出允许的工作区范围: {_WORKSPACE_ROOT}"
        )
    return candidate


@tool
def read_file(file_path: str) -> str:
    """读取指定文件的内容。

    Args:
        file_path: 要读取的文件路径（相对或绝对路径，必须在工作区内）。

    Returns:
        文件内容字符串。若文件不存在或无法读取，返回错误说明。
    """
    try:
        target = _resolve_path(file_path)
    except PermissionError as e:
        return f"[错误] {e}"
    if not target.exists():
        return f"[错误] 文件不存在: {file_path}"
    if not target.is_file():
        return f"[错误] 不是文件: {file_path}"
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[错误] 读取文件失败: {e}"
    # 限制单次返回大小，避免上下文溢出
    if len(content) > 20000:
        content = content[:20000] + "\n... [文件过长，已截断]"
    return content


@tool
def list_dir(dir_path: str = ".") -> str:
    """列出指定目录下的文件和子目录。

    Args:
        dir_path: 目录路径，默认为当前工作目录。

    Returns:
        目录内容列表，区分文件与子目录。
    """
    try:
        target = _resolve_path(dir_path)
    except PermissionError as e:
        return f"[错误] {e}"
    if not target.exists():
        return f"[错误] 目录不存在: {dir_path}"
    if not target.is_dir():
        return f"[错误] 不是目录: {dir_path}"
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception as e:
        return f"[错误] 列出目录失败: {e}"

    lines: List[str] = []
    for entry in entries:
        prefix = "[DIR] " if entry.is_dir() else "[FILE]"
        lines.append(f"{prefix} {entry.name}")
    if not lines:
        return "(空目录)"
    return "\n".join(lines)


@tool
def search_code(pattern: str, path: str = ".", file_type: str = "") -> str:
    """在代码文件中搜索匹配的内容（正则表达式）。

    Args:
        pattern: 要搜索的正则表达式模式。
        path: 搜索起始路径，默认为当前目录。
        file_type: 限定文件后缀（如 .py、.js），留空表示搜索所有文本文件。

    Returns:
        匹配结果，包含文件名、行号和匹配行内容。
    """
    try:
        target = _resolve_path(path)
    except PermissionError as e:
        return f"[错误] {e}"
    if not target.exists():
        return f"[错误] 路径不存在: {path}"

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"[错误] 无效的正则表达式: {e}"

    # 需要跳过的目录
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    results: List[str] = []
    match_count = 0
    max_matches = 100

    for root, dirs, files in os.walk(target):
        # 原地修改 dirs 以剪枝
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if file_type and not fname.endswith(file_type):
                continue
            fpath = Path(root) / fname
            # 跳过二进制文件
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = fpath.relative_to(_WORKSPACE_ROOT)
                            results.append(f"{rel}:{lineno}: {line.rstrip()}")
                            match_count += 1
                            if match_count >= max_matches:
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if match_count >= max_matches:
                break
        if match_count >= max_matches:
            break

    if not results:
        return f"未找到匹配 '{pattern}' 的内容"
    output = "\n".join(results)
    if match_count >= max_matches:
        output += f"\n... [达到 {max_matches} 条上限，结果已截断]"
    return output


@tool
def execute_code(code: str, timeout: int = 10) -> str:
    """在隔离的子进程中执行 Python 代码并返回输出。

    Args:
        code: 要执行的 Python 代码字符串。
        timeout: 超时时间（秒），默认 10 秒。

    Returns:
        代码的标准输出和标准错误。超时或异常会被捕获并返回说明。
    """
    # 安全限制：禁止使用 __import__、os.system、subprocess 等危险操作
    forbidden = ["__import__", "os.system", "subprocess", "exec(", "eval("]
    for kw in forbidden:
        if kw in code:
            return f"[错误] 代码包含被禁止的操作: {kw}"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    # 构造子进程环境，强制使用 UTF-8 输出，避免 Windows 下 GBK 解码错误
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        output = ""
        if result.stdout:
            output += f"[stdout]\n{result.stdout}"
        if result.stderr:
            output += f"[stderr]\n{result.stderr}"
        if not output:
            output = "(代码执行完毕，无输出)"
        return output
    except subprocess.TimeoutExpired:
        return f"[错误] 代码执行超时（超过 {timeout} 秒）"
    except Exception as e:
        return f"[错误] 执行失败: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def get_tools() -> list:
    """返回 Agent 可用的工具列表。"""
    return [read_file, list_dir, search_code, execute_code]
