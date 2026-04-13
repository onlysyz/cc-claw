# CC-Claw：Claude Code 的 autonomous AI 编程 Agent

[![GitHub stars](https://img.shields.io/github/stars/onlysyz/cc-claw?style=for-the-badge)](https://github.com/onlysyz/cc-claw/stargazers)
[![PyPI version](https://img.shields.io/pypi/v/cc-claw?style=for-the-badge)](https://pypi.org/project/cc-claw/)
[![Python versions](https://img.shields.io/pypi/pyversions/cc-claw?style=for-the-badge)](https://pypi.org/project/cc-claw/)
[![License](https://img.shields.io/github/license/onlysyz/cc-claw?style=for-the-badge)](LICENSE)

<p align="center">
  <strong>CC-Claw 是一款 autonomous AI 工作伴侣，将 Claude Code 转变为不知疲倦的编程伙伴 —— 持续执行任务、分解目标，在你睡觉时也在工作。</strong>
</p>

<p align="center">
  <a href="#核心功能">核心功能</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#使用示例">使用示例</a> ·
  <a href="#架构设计">架构</a> ·
  <a href="#常见问题">FAQ</a>
</p>

---

## 什么是 CC-Claw？

**CC-Claw** 是一个运行在后台的 AI Agent 守护进程，让 Claude Code CLI 拥有了**自主工作能力**。

### 核心价值

| 传统方式 | CC-Claw |
|----------|---------|
| ❌ 需要人工时时刻刻指导 | ✅ 设置目标后自动执行 |
| ❌ 会话结束上下文丢失 | ✅ 持久化记忆跨会话 |
| ❌ 遇到错误就停止 | ✅ 智能重试自动恢复 |
| ❌ 只能串行执行任务 | ✅ 多 Agent 并行协作 |
| ❌ 只能在你醒着时工作 | ✅ 24/7 持续运行 |

---

## 核心功能

- 🎯 **目标驱动** — 自动分解目标为可执行任务
- ⚡ **自主执行** — 24/7 自动运行，无需人工干预
- 🧠 **持久化记忆** — 跨会话记忆上下文和决策
- 🔄 **智能重试** — 指数退避 + 熔断器容错
- 👥 **多 Agent 协作** — 多个 Agent 同时工作
- 📊 **Token 管理** — 自动规避限流，智能节流
- 🔒 **本地执行** — 所有代码执行在本地完成
- 🕒 **定时任务** — 支持延迟任务调度
- 📋 **任务队列** — 优先级队列，重要任务优先
- 🔔 **进度通知** — 里程碑完成时主动通知

---

## 快速开始

### 安装

```bash
pip install cc-claw
```

### 初始化

```bash
cc-claw pair    # 注册设备
cc-claw daemon  # 启动守护进程
```

### 设置目标

```
发送: /goal 实现用户认证系统
```

CC-Claw 会自动分解目标并开始执行！

---

## 使用示例

### 基本命令

```bash
cc-claw start        # 启动守护进程
cc-claw progress     # 查看进度
cc-claw pause        # 暂停
cc-claw resume       # 恢复
```

### 机器人命令

| 命令 | 描述 |
|------|------|
| `/start` | 开始使用 |
| `/progress` | 查看进度 |
| `/pause` | 暂停 |
| `/resume` | 恢复 |
| `/goals` | 管理目标 |

---

## 架构设计

```
用户 (Telegram/Lark) → CC-Claw Cloud → 本地设备 → Claude Code CLI
                                       ↑
                    进度报告 ← ———— 结果/新任务
```

### 组件

| 组件 | 描述 |
|------|------|
| Goal Engine | 目标 → 任务分解 |
| Task Queue | 优先级任务队列 |
| Persistent Memory | 跨会话上下文 |
| Multi-Agent | 多 Agent 协作 |
| Smart Retry | 指数退避 + 熔断器 |
| Token Tracker | Token 使用追踪 |

---

## 常见问题

### Q: 和 GitHub Copilot 有什么区别？

| 特性 | Copilot | CC-Claw |
|------|---------|---------|
| 交互方式 | IDE 插件 | 守护进程 |
| 运行时间 | 编码时 | 24/7 |
| 任务执行 | 代码补全 | 完整任务 |

### Q: Token 用完会怎样？

自动等待 Token 刷新后恢复。

### Q: 支持哪些平台？

- macOS ✅
- Linux ✅
- Windows (WSL) ✅

---

## 相关资源

- 📖 文档: [docs.cc-claw.dev](https://docs.cc-claw.dev)
- 💬 Discord: [discord.gg/cc-claw](https://discord.gg/cc-claw)
- 🐦 Twitter: [@ccclaw](https://twitter.com/ccclaw)

---

<p align="center">
  <strong>给个 ⭐ 支持一下！</strong>
</p>