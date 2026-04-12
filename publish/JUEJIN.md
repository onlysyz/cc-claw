# 掘金文章 — CC-Claw: 让你的 Claude Code Tokens 24/7 不停工作

---

## 文章标题

**主标题：** 我用 Claude Code Plan 做了一个 24/7 自动工作的 AI 助手

**副标题：** 设定目标 → 自动分解任务 → 执行 → 循环直到完成。睡觉的时候它也在工作。

---

## 文章正文

### 先问一个问题

你每个月的 Claude Code Plan 用完了吗？

我猜答案是：没有。

大多数开发者的 tokens 90% 的时间都在闲置。聊天、等待、复制粘贴。手动的工作流，还要被 429 错误折腾。

我就是这么开始的。

---

### 解决方案：CC-Claw

CC-Claw 是一个**自主 AI 工作伙伴**，把你的 Claude Code tokens 变成 24/7 不停工作的生产力。

**它怎么工作的：**

```
你 (Telegram/Lark) → CC-Claw 云端 → 你的设备 → Claude Code CLI
                              ↑                              ↓
                   进度报告 ← ─────── 结果 / 新任务
```

1. **设置目标** — 通过 Telegram 或 Lark 发送你的目标
2. **任务分解** — AI 自动将目标分解成可执行的步骤
3. **自主执行** — Claude Code 在你的机器上执行任务（不是云端）
4. **智能节流** — 遇到 429 限流？停止、等待、每小时检查、token 恢复后继续

---

### 核心特性

| 特性 | 说明 |
|------|------|
| 🎯 **目标驱动** | 为你的目标工作，不是简单回答问题 |
| ⚡ **自主循环** | 任务 → 执行 → 下一个 → 重复，直到目标完成 |
| 🏖️ **智能休息** | 429 时停止，每小时检查，token 恢复后继续 |
| 🔝 **优先队列** | 紧急指令跳到最前面 |
| 🤫 **静默模式** | 不主动打扰，只在需要时报告 |
| 🔒 **隐私安全** | 所有执行都在本地机器完成 |

---

### 内置工具（8个实用类）

| 工具 | 功能 |
|------|------|
| **FileProcessor** | 读写文件、搜索、统计行数 |
| **DataScraper** | 抓取网页、提取链接/邮箱/IP |
| **ApiClient** | HTTP 调用，支持认证 |
| **ProcessManager** | 列出/杀死进程 |
| **SystemInfo** | 磁盘、内存、CPU |
| **GitHelper** | status、diff、log、branch |
| **DockerHelper** | ps、logs、restart |

---

### 实际效果

我告诉 CC-Claw：「为我的 Express API 实现 JWT 用户认证」

结果（睡前设置，睡醒检查）：

```
✅ User model（bcrypt 密码加密）
✅ JWT 中间件
✅ 登录/注册接口
✅ 受保护路由
✅ Jest 测试用例

6 个任务，6 分钟，0 干预
```

**Token 消耗：** 8,234 tokens
**自主工作时间：** 6 分钟（vs 手动估计 30 分钟）

---

### 和其他工具的区别

| 工具 | CC-Claw 的优势 |
|------|---------------|
| Cursor / Copilot | CC-Claw 是目标导向的自主执行，不是聊天替代品 |
| 传统 CI/CD | CC-Claw 能理解代码库上下文，智能决策 |
| 定时任务 | CC-Claw 有 AI 驱动的任务分解，不是死板的脚本 |

---

### 快速开始

**服务端部署：**

```bash
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw
pip install -e .
cp .env.example .env
# 编辑 .env 添加你的 TELEGRAM_BOT_TOKEN
python run_server.py
```

**客户端安装：**

```bash
pip install -e .
cc-claw install
```

**开始使用：**

1. Telegram 搜索 Bot，发送 `/start`
2. 完成 onboarding（职业、目标、「成功」的定义）
3. 设置你的第一个目标
4. 剩下的交给 CC-Claw

---

### 适合谁用？

- **有 Claude Code Plan 但用不完的开发者**
- **想要自动化重复开发任务的人**
- **需要 24/7 不停工作的 AI 助手**
- **想让 AI 在你睡觉时也在工作的人**

---

### 开源地址

**GitHub:** https://github.com/onlysyz/cc-claw

**演示页面:** https://cc-claw.dev/demo

---

### 写在最后

Token 是资源。不用就是浪费。

CC-Claw 让每一颗 token 都物有所值。

如果你也有 Claude Code Plan，不妨试试。

---

## 标签建议

```
#AI #ClaudeCode #人工智能 #自动化 #开发者工具
#效率工具 #编程 #副业 #工作流自动化 #Python
```

---

## 发布时间建议

- **掘金：** 周三、周四 下午 2-4 点
- **热榜技巧：** 文章发布后 1 小时内回复所有评论，增加互动