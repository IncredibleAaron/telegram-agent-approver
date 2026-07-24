# Telegram Agent Approver 📱⚡

跨端 **Human-in-the-Loop (HITL)** 远程审批工具与标准 MCP (Model Context Protocol) 服务器。

专为 AI Coding Agent (如 Antigravity IDE, Cursor, VSCode, Claude Desktop) 及命令行自动化脚本设计。当 Agent 或脚本计划执行高风险操作（如 `git push --force`、部署生产环境、删除文件、修改敏感配置）时，自动向用户的手机 Telegram 发送带 **[✅ 批准执行]** 和 **[❌ 拒绝]** 按键的消息卡片，在手机上点击确认后解除电脑端挂起。

---

## ✨ 核心特性

- **零公网配置 (Zero Tunnel)**：利用 Telegram 官方 Bot 的长轮询 (Long Polling) 机制，无需公网 IP、内网穿透或 Cloudflare Tunnel。
- **全平台支持 (MCP Compatible)**：原生提供标准 MCP Server，无缝兼容 Antigravity IDE、Cursor、Windsurf、VSCode 及 Claude Desktop。
- **CLI 命令行直用**：支持直接在 Terminal / PowerShell / Git Pre-push Hooks 中独立使用。
- **现代 Python 工具链**：基于 `uv`、`ruff` 及 `ty` 构建，代码极其轻量安全。

---

## 🚀 快速开始

### 1. 安装依赖

使用 [uv](https://github.com/astral-sh/uv) 一键安装依赖：

```bash
uv sync
```

### 2. 配置 Telegram 凭证

在项目根目录下复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

填入您的 Telegram凭证：
- `TELEGRAM_BOT_TOKEN`: 在 Telegram 中联系 `@BotFather` 创建 Bot 获取。
- `TELEGRAM_CHAT_ID`: 在 Telegram 中联系 `@userinfobot` 获取。

> ⚠️ **注意**：初次使用前，请先在手机 Telegram 中搜索您的 Bot 并点击 **Start** 激活对话。

---

## 🛠️ 配置为 MCP Server

在您的 AI 编辑器配置（如 Antigravity IDE 的 `mcp_config.json` 或 `claude_desktop_config.json`）中添加以下配置：

```json
{
  "mcpServers": {
    "telegram-approver": {
      "command": "uv",
      "args": [
        "--directory",
        "D:/repos/telegram_agent_approver",
        "run",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

---

## 💻 命令行 CLI 独立使用

你可以在任意 Bash / PowerShell 脚本或 Git Pre-push Hook 中直接调用 CLI：

```bash
uv run python cli.py "生产环境部署确认" "准备部署 commit 7a8b9c 到 prod-server" --timeout 120
```

---

## 🧪 质量门禁 (Quality Gate)

项目遵循 Astral Modern Python 工具链规范：

```bash
# 代码检查与自动修复
uv run ruff check --fix .

# 类型检查
uv run ty check .
```

---

## 📄 License

MIT
