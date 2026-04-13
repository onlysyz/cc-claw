# CC-Claw: Autonomous AI Coding Agent for Claude Code

<!-- SEO-Optimized Badges -->
[![GitHub stars](https://img.shields.io/github/stars/onlysyz/cc-claw?style=for-the-badge)](https://github.com/onlysyz/cc-claw/stargazers)
[![PyPI version](https://img.shields.io/pypi/v/cc-claw?style=for-the-badge)](https://pypi.org/project/cc-claw/)
[![Python versions](https://img.shields.io/pypi/pyversions/cc-claw?style=for-the-badge)](https://pypi.org/project/cc-claw/)
[![License](https://img.shields.io/github/license/onlysyz/cc-claw?style=for-the-badge)](LICENSE)
[![Discord](https://img.shields.io/discord/123456789?style=for-the-badge)](https://discord.gg/cc-claw)
[![Twitter Follow](https://img.shields.io/twitter/follow/ccclaw?style=for-the-badge)](https://twitter.com/ccclaw)

<!-- Main tagline with primary keywords -->
<h1 align="center">
  <strong>CC-Claw: 让 Claude Code 24/7 自动编程的 AI Agent</strong>
</h1>

<p align="center">
  <strong>CC-Claw is an autonomous AI working companion that turns Claude Code into a tireless coding partner — continuously executing tasks, breaking down goals, and making progress while you sleep.</strong>
</p>

<p align="center">
  <a href="https://github.com/onlysyz/cc-claw"><strong>English</strong></a> ·
  <a href="https://github.com/onlysyz/cc-claw/blob/main/README_CN.md"><strong>中文</strong></a>
</p>

<p align="center">
  <a href="#核心功能">核心功能</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#使用示例">使用示例</a> ·
  <a href="#架构设计">架构</a> ·
  <a href="#常见问题">FAQ</a> ·
  <a href="#相关资源">资源</a>
</p>

---

## 什么是 CC-Claw？

**CC-Claw** 是一个运行在后台的 AI Agent守护进程，让 Claude Code CLI 拥有了**自主工作能力**。

传统 AI 编程工具需要你时时刻刻指导它工作。CC-Claw 改变了这一点：

- 你设置目标，它自动分解成可执行任务
- 它 24/7 自动执行，无需人工干预
- 遇到 API 限流自动等待，恢复后继续
- 跨会话记忆上下文，工作进度不丢失

> **"凡 token 消耗，皆有利于我。"**

---

## 核心功能

| 功能 | 描述 | 关键词 |
|------|------|--------|
| 🎯 **目标驱动** | 自动分解目标为可执行任务 | goal decomposition, task automation |
| ⚡ **自主执行** | 24/7 自动运行，无需人工干预 | autonomous agent, 24/7 coding |
| 🧠 **持久化记忆** | 跨会话记忆上下文和决策 | persistent context, memory |
| 🔄 **智能重试** | 指数退避 + 熔断器容错 | exponential backoff, circuit breaker |
| 📊 **Token 管理** | 自动规避限流，智能节流 | token management, rate limit |
| 🔒 **本地执行** | 所有代码执行在本地完成 | local execution, privacy |
| 🕒 **定时任务** | 支持延迟任务调度 | scheduled tasks, cron |
| 📋 **任务队列** | 优先级队列，重要任务优先 | priority queue, task queue |
| 🔔 **进度通知** | 里程碑完成时主动通知 | notifications, progress |

---

## 快速开始

### 前置要求

- Python 3.9+
- Claude Code CLI ([安装指南](https://docs.anthropic.com/en/docs/claude-code))
- 网络连接（用于调用 Claude API）

### 安装

```bash
# 从 PyPI 安装
pip install cc-claw

# 或从源码安装
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw
pip install -e .
```

### 飞书（Feishu）本地安装最佳实践

飞书集成让你可以在 Lark/Feishu 机器人中直接与 CC-Claw 对话。

#### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

#### 2. 配置飞书机器人

在 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用，获取以下信息：

- **App ID**: `cli_xxxxxxxx`
- **App Secret**: `xxxxxxxxxxxxxxxx`
- **Bot Feature** → 开启「机器人」能力

在「事件订阅」中添加以下订阅：
- `im.message.receive_v1`（接收消息）

在「权限管理」中添加：
- `im:message`
- `im:message.group_at_msg`
- `im:message.p2p_msg`

#### 3. 配置 .env 文件

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# 服务器配置
HOST=0.0.0.0
API_PORT=4000
WS_PORT=4001

# 飞书配置
LARK_APP_ID=cli_xxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxxxxxx
LARK_BOT_NAME=CC-Claw

# MiniMax API（用于目标分解，省 Token）
ANTHROPIC_API_KEY=sk-xxxxxxxx
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# Claude Code 配置（在客户端设置）
# CLAUDE_PATH=/usr/local/bin/claude
```

#### 4. 启动服务器

```bash
# 启动 API + WebSocket 服务器
python run_server.py

# 服务器日志显示 "WebSocket server started on 0.0.0.0:4001" 表示成功
```

#### 5. 使用 ngrok 暴露本地服务器（如需公网访问）

```bash
# 安装 ngrok
# macOS: brew install ngrok
# Linux: sudo apt install ngrok

# 启动隧道
ngrok http 4001

# 记录输出的 WebSocket URL，如：wss://xxxx.ngrok.io
```

#### 6. 配置飞书机器人事件请求地址

在飞书开放平台 → 你的应用 → 事件订阅：

- **请求地址 URL**: `https://your-domain.com/webhook/lark`
- 如果使用 ngrok：`https://xxxx.ngrok.io/webhook/lark`

#### 7. 启动客户端（配对设备）

```bash
# 先配置服务器地址
python3 -m cli config --set server_ws_url=ws://localhost:4001
python3 -m cli config --set server_api_url=http://localhost:4000

# 设置工作目录（Claude Code 在此目录下工作）
python3 -m cli config --set working_dir=/path/to/your/project

# 设置权限模式（跳过授权确认，否则 Claude 会等待交互）
python3 -m cli config --set permission_mode=bypassPermissions

# 然后进行配对
python3 -m cli pair

# 8. 启动守护进程
python3 -m cli start
```

#### 8. 在飞书中使用

给机器人发送命令：

| 命令 | 描述 |
|------|------|
| `/start` | 开始使用 + 引导设置 |
| `/goal <目标>` | 设置新目标（如：`/goal 帮我写一个博客系统`） |
| `/progress` | 查看进度和 Token 统计 |
| `/pause` | 暂停自主执行 |
| `/resume` | 恢复自主执行 |
| `/tasks` | 查看任务队列 |
| `/goals` | 管理目标 |
| `/setgoal <id>` | 切换工作目标 |
| `/newgoal <描述>` | 创建新目标 |
| `/deltask <id>` | 删除任务 |
| `/help` | 帮助 |

#### 9. 常见问题排查

```bash
# 查看服务器日志
tail -f logs/server.log

# 查看客户端日志
python3 -m cli status

# 重启服务
pkill -f run_server.py && python3 -m server.run &
```

---

### 设置第一个目标

```
在 飞书/Telegram 中发送：
/goal  实现用户认证系统

CC-Claw 会自动：
1. 询问你的职业和现状
2. 分解目标为具体任务
3. 开始自主执行
```

---

## 使用示例

### 基本命令

```bash
python3 -m cli start        # 启动守护进程
python3 -m cli status       # 查看连接状态
python3 -m cli progress     # 查看目标进度
python3 -m cli pause        # 暂停自主模式
python3 -m cli resume       # 恢复自主模式
python3 -m cli goals        # 查看所有目标
python3 -m cli tasks        # 查看任务队列
```

### 机器人命令

| 命令 | 描述 |
|------|------|
| `/start` | 开始使用 + 引导设置 |
| `/progress` | 查看目标进度和 Token 统计 |
| `/pause` | 暂停自主执行 |
| `/resume` | 恢复自主执行 |
| `/tasks` | 查看当前任务队列 |
| `/goals` | 管理目标 |
| `/setgoal <id>` | 切换工作目标 |
| `/status` | 查看连接状态 |
| `/help` | 帮助 |

### 代码示例：Python API

```python
from cc_claw import CCClawDaemon, ClientConfig

# 配置
config = ClientConfig(
    device_id="your-device-id",
    device_token="your-device-token",
    claude_path="/usr/local/bin/claude"
)

# 启动守护进程
daemon = CCClawDaemon(config)
daemon.run()
```

### 使用持久化记忆

```python
from cc_claw import PersistentMemory, ConversationMemory

# 长期记忆
memory = PersistentMemory()
memory.add_context_snapshot(
    task="实现支付模块",
    context="使用 Stripe API",
    result="完成支付流程"
)

# 获取恢复上下文
resume = memory.get_context_for_resume()

# 短期对话历史
conv = ConversationMemory()
conv.add_user("继续上次的工作")
conv.add_assistant("好的，上次你在实现支付模块...")
```

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Cloud Server                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Telegram    │  │   API       │  │  WebSocket Server       │ │
│  │ Bot / Lark  │  │   Server   │  │  (persistent connection) │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ WSS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Your Device (Local)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Gateway     │  │ Goal Engine │  │  Claude Code CLI        │ │
│  │ Client      │  │ Task Queue  │  │  (executes tasks)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │Persistent   │  │Multi-Agent  │  │  Smart Retry           │ │
│  │Memory       │  │Collaboration│  │  (backoff + breaker)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 路径 | 描述 |
|------|------|------|
| **Goal Engine** | `client/goal_engine.py` | 将目标分解为可执行任务 |
| **Task Queue** | `client/task_queue.py` | 优先级任务队列 |
| **Persistent Memory** | `client/memory.py` | 跨会话上下文持久化 |
| **Smart Retry** | `client/retry.py` | 指数退避 + 熔断器 |
| **Token Tracker** | `client/token_tracker.py` | Token 使用量追踪 |

---

## 常见问题

### Q: CC-Claw 和 GitHub Copilot有什么区别？

| 特性 | GitHub Copilot | CC-Claw |
|------|---------------|---------|
| 交互方式 | IDE 插件，实时补全 | 守护进程，目标驱动 |
| 运行时间 | 仅在你编码时 | 24/7 持续工作 |
| 任务执行 | 单行代码补全 | 完整任务自主执行 |
| 记忆能力 | 无 | 持久化上下文 |

### Q: Token 用完会怎样？

CC-Claw 有完善的 Token 管理机制：
- 接近限流时自动减速
- 遇到 429 错误自动等待
- Token 刷新后自动恢复

### Q: 本地执行安全吗？

是的。所有代码执行都在你的本地机器上完成，CC-Claw 只是调用 Claude Code CLI，不上传你的代码。

### Q: 支持哪些平台？

- macOS ✅
- Linux ✅
- Windows (WSL) ✅

### Q: 如何贡献代码？

```bash
# Fork 后
git clone https://github.com/your-fork/cc-claw.git
cd cc-claw
pip install -e ".[dev]"
pytest tests/
```

---

## Star 历史

[![Star History](https://api.star-history.com/svg?repos=onlysyz/cc-claw&type=Date)](https://star-history.com/#onlysyz/cc-claw&Date)

---

## License

MIT License - 详见 [LICENSE](LICENSE)

---

<p align="center">
  <strong>如果你觉得 CC-Claw 有用，给个 ⭐ 支持一下！</strong>
</p>