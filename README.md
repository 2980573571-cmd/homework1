# Code Explanation Agent

一个基于 LangChain 构建的**代码解释助手 Agent**，具备 LLM 调用、Prompt 设计、工具集成、上下文记忆和错误重试等核心 Agent 能力。

## 功能特性

- 📖 **代码逻辑解释**：用通俗易懂的语言解释代码做了什么、怎么做的、为什么这样做
- 📝 **注释生成**：为缺少注释的代码生成清晰的中文注释（docstring + 行内注释）
- ❓ **代码问答**：回答关于代码的任何问题（时间复杂度、引用关系、执行流程等）
- 🛠️ **工具集成**：文件读取、代码搜索、目录列表、代码执行
- 🧠 **上下文记忆**：支持多轮对话，理解上下文
- 🔄 **错误重试**：针对网络/速率限制等瞬时故障自动重试
- 🌐 **多云兼容**：支持所有 OpenAI 兼容接口（DeepSeek / 通义千问 / Kimi / 智谱 / OpenAI 等）
- 💻 **CLI 交互**：美观的终端界面，支持交互模式与单次查询模式
- 🌐 **Web 界面**：Streamlit 聊天式网页，支持流式输出与工具调用展示

## 项目结构

```
homework1/
├── main.py              # CLI 入口（交互模式 / 单次查询）
├── webapp.py            # Web 界面（Streamlit 聊天式交互，流式输出）
├── config.py            # 配置管理（LLM / Agent 参数）
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量模板
├── agent/
│   ├── __init__.py
│   ├── core.py          # Agent 核心循环（输入→推理→工具调用→输出）
│   ├── tools.py         # 工具集（读文件/搜索/列目录/执行代码）
│   ├── prompts.py       # Prompt 设计
│   └── memory.py        # 上下文记忆
├── examples/
│   └── sample_code.py   # 示例代码（用于测试解释功能）
├── README.md
└── Design.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 LLM

复制 `.env.example` 为 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`，以下以 DeepSeek 为例：

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

> 其他服务商配置示例见 `.env.example` 注释。

### 3. 运行

**交互模式**：

```bash
python main.py
```

**单次查询模式**：

```bash
python main.py "解释 examples/sample_code.py 的逻辑"
```

**Web 界面**：

```bash
streamlit run webapp.py
```

## 使用示例

进入交互模式后，可以：

```
解释 examples/sample_code.py 的逻辑
```

```
为这段代码生成中文注释: <粘贴代码>
```

```
average_age 函数的时间复杂度是多少？
```

```
搜索 add_user 方法在哪里被调用
```

## 技术栈

- **语言**：Python 3.10+
- **Agent 框架**：LangChain 1.x
- **LLM**：OpenAI 兼容接口（ChatOpenAI）
- **CLI**：rich
- **Web 界面**：Streamlit

## 许可

MIT License
