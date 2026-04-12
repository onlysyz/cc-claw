# CC-Claw - 详细设计文档

## 1. 项目概述

### 1.1 项目背景

CC-Claw 是一个让用户通过 Telegram 机器人远程控制本地 Claude Code CLI 的网关服务。用户在 Telegram 上发送消息，消息通过网关转发到用户本地运行的客户端，客户端调用 Claude Code CLI 执行任务后将结果返回给用户。

### 1.2 项目目标

- **核心目标**：通过 Telegram 机器人实现远程调用本地 Claude Code CLI
- **用户体验**：用户无需暴露公网 IP 或配置复杂网络，通过简单的配对流程即可使用
- **安全性**：消息加密传输，支持配对验证，防止未授权访问
- **扩展性**：支持多用户、多设备管理

### 1.3 对标产品

- **OpenClaw**：参考其 Gateway WebSocket 网络架构
- **Carter（Lobster）**：Telegram AI 助手实现参考

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     云端服务 (Cloud Server)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Telegram Bot   │  │   API Server    │  │  WebSocket     │ │
│  │  (消息入口)      │  │   (REST API)    │  │  Server        │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│           └────────────────────┼────────────────────┘          │
│                                ▼                               │
│                    ┌─────────────────────┐                     │
│                    │    Message Broker   │                     │
│                    │    (Redis Pub/Sub)  │                     │
│                    └──────────┬──────────┘                     │
└────────────────────────────────┼────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     用户设备 (User Device)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Gateway       │  │  Claude Code   │  │  Tools          │ │
│  │  (客户端守护进程) │  │     CLI        │  │  (截屏/文件等)   │ │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘ │
│           │                    │                                │
│           └────────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 组件说明

| 组件 | 位置 | 职责 |
|------|------|------|
| Telegram Bot | 云端 | 接收用户消息、发送响应、管理机器人命令 |
| API Server | 云端 | 用户注册、配对管理、设备管理 |
| WebSocket Server | 云端 | 与本地 Gateway 建立长连接、消息路由 |
| Message Broker | 云端 | 跨服务消息传递（Redis Pub/Sub） |
| Gateway 客户端 | 用户设备 | 本地 WebSocket 客户端、执行 Claude CLI |
| Claude Code CLI | 用户设备 | 执行 AI 对话任务 |

### 2.3 部署拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                        云端 (VPS/云服务器)                        │
│  - Telegram Bot (独立进程)                                      │
│  - API Server (REST API)                                       │
│  - WebSocket Server                                            │
│  - Redis (消息队列)                                            │
│  - PostgreSQL (持久化存储)                                      │
└─────────────────────────────────────────────────────────────────┘
                                 ▲
                                 │ HTTPS/WSS
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       用户设备 (Mac/PC/Linux)                    │
│  - Gateway 守护进程 (launchd/systemd)                           │
│  - Claude Code CLI                                              │
│  - 工具集 (截屏、文件管理等)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心功能

### 3.1 消息收发

- **文本消息**：用户发送文本，Gateway 转发给本地 Claude CLI，响应返回给用户
- **图片消息**：支持发送图片给 Claude（作为上下文或分析）
- **语音消息**：语音转文字后转发
- **文件消息**：支持文件上传和下载

### 3.2 配对机制

```
用户首次使用:
1. 用户在机器人输入 /pair 命令
2. 机器人生成 6 位配对码 (如: ABC123)
3. 用户在本地 Gateway 输入配对码
4. 客户端连接服务器并验证配对码
5. 配对成功后，Telegram ID 与设备绑定
```

### 3.3 会话管理

- **单轮对话**：每次消息独立处理
- **多轮对话**：保持会话上下文（可选）
- **会话超时**：无活动 10 分钟后自动结束会话

### 3.4 工具集成

| 工具 | 功能 | 实现方式 |
|------|------|----------|
| 截屏 | 获取屏幕截图 | screencapture (macOS) / scrot (Linux) |
| 文件列表 | 查看目录文件 | ls 命令 |
| 文件读取 | 读取文件内容 | cat/readfile |
| 文件写入 | 写入文件 | echo/写入操作 |
| Shell 执行 | 执行 shell 命令 | subprocess |
| 进程管理 | 查看/结束进程 | ps/kill |

### 3.5 命令系统

```
/start - 欢迎信息
/pair - 开始配对
/unpair - 解除配对
/status - 查看连接状态
/settings - 设置选项
/help - 帮助信息
/stop - 停止当前会话
```

---

## 4. 消息流程

### 4.1 配对流程

```
┌──────────┐     /pair      ┌──────────┐
│  用户    │ ────────────▶ │ Telegram │
│ (Telegram)│               │   Bot    │
└──────────┘               └────┬─────┘
                                 │ 生成配对码
                                 ▼
┌──────────┐     配对码      ┌──────────┐
│  用户    │ ◀──────────── │ API      │
│          │               │ Server   │
└──────────┘               └────┬─────┘
                                 │ 存储配对码
                                 ▼
┌──────────┐   输入配对码    ┌──────────┐
│ 本地     │ ────────────▶ │ Gateway  │
│ Gateway  │               │ 客户端   │
└────┬─────┘               └────┬─────┘
     │ 验证配对                  │
     │ WSS 连接                  │
     ▼                          ▼
┌──────────┐   配对成功    ┌──────────┐
│ API      │ ◀────────── │ WebSocket│
│ Server   │             │ Server   │
└──────────┘             └──────────┘
```

### 4.2 消息处理流程

```
┌──────────┐   发送消息   ┌──────────┐
│  用户    │ ──────────▶ │ Telegram │
│          │             │   Bot    │
└──────────┘             └────┬─────┘
                              │ 消息 + user_id
                              ▼
┌──────────┐              ┌──────────┐
│ WebSocket│ ◀─────────── │  Message  │
│ Client   │    消息      │  Broker   │
└────┬─────┘              └──────────┘
     │ 转发消息
     ▼
┌──────────┐   claude -p  ┌──────────┐
│ Claude   │ ◀─────────── │ Gateway  │
│   CLI    │   prompt    │ 客户端   │
└────┬─────┘              └────┬─────┘
     │ 返回结果                 │
     │ (流式/完整)             │
     ▼                         ▼
┌──────────┐   返回结果    ┌──────────┐
│ WebSocket│ ───────────▶ │  Message │
│ Client   │              │  Broker  │
└────┬─────┘              └────┬─────┘
     │                          │ 消息 + chat_id
     │                          ▼
     │                    ┌──────────┐
     │                    │ Telegram │
     │                    │   Bot    │
     │                    └────┬─────┘
     │                          │ 发送响应
     ▼                          ▼
     └─────────────────▶  ┌──────────┐
                           │  用户    │
                           └──────────┘
```

---

## 5. API 设计

### 5.1 REST API

#### 5.1.1 用户相关

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/auth/register | 用户注册 | - |
| POST | /api/auth/login | 用户登录 | - |
| GET | /api/user/profile | 获取用户信息 | JWT |
| PUT | /api/user/profile | 更新用户信息 | JWT |

#### 5.1.2 设备相关

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/devices | 获取设备列表 | JWT |
| POST | /api/devices | 注册新设备 | JWT |
| DELETE | /api/devices/:id | 删除设备 | JWT |
| GET | /api/devices/:id/status | 获取设备状态 | JWT |

#### 5.1.3 配对相关

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/pairing/generate | 生成配对码 | - |
| POST | /api/pairing/verify | 验证配对码 | - |
| POST | /api/pairing/complete | 完成配对 | Device Token |
| GET | /api/pairing/status | 查询配对状态 | - |

### 5.2 WebSocket 消息协议

#### 5.2.1 客户端 -> 服务器

```json
// 注册消息
{
  "type": "register",
  "device_id": "device_xxx",
  "token": "device_token_xxx"
}

// 发送消息
{
  "type": "message",
  "message_id": "msg_xxx",
  "content": "用户消息内容",
  "timestamp": 1699999999
}

// 消息确认
{
  "type": "ack",
  "message_id": "msg_xxx"
}
```

#### 5.2.2 服务器 -> 客户端

```json
// 收到消息
{
  "type": "message",
  "message_id": "msg_xxx",
  "chat_id": "telegram_chat_id",
  "user_id": "telegram_user_id",
  "content": "用户消息内容",
  "timestamp": 1699999999
}

// 消息已送达
{
  "type": "delivered",
  "message_id": "msg_xxx"
}

// 错误消息
{
  "type": "error",
  "code": "AUTH_FAILED",
  "message": "认证失败"
}
```

### 5.3 Telegram Bot Webhook

| 事件 | 路径 | 描述 |
|------|------|------|
| POST | /webhook/message | 接收消息 |
| POST | /webhook/callback | 回调（如内联键盘） |

---

## 6. 数据模型

### 6.1 数据库设计 (PostgreSQL)

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 设备表
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL, -- macos, linux, windows
    status VARCHAR(20) DEFAULT 'offline', -- online, offline
    last_seen_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 设备令牌表
CREATE TABLE device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 配对表
CREATE TABLE pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(6) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id),
    device_id UUID REFERENCES devices(id),
    status VARCHAR(20) DEFAULT 'pending', -- pending, completed, expired
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 会话表
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    message_count INTEGER DEFAULT 0
);

-- 消息日志表
CREATE TABLE message_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    direction VARCHAR(10) NOT NULL, -- inbound, outbound
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 6.2 Redis 数据结构

```redis
# 设备连接状态
DEVICE:{device_id}:STATUS -> "online" | "offline"

# WebSocket 连接映射
WS:USER:{telegram_id} -> device_id

# 消息队列
QUEUE:MESSAGE:{device_id} -> [pending messages]

# 配对码临时存储
PAIRING:{code} -> {user_id, expires_at}

# 会话状态
SESSION:{session_id}:CONTEXT -> [conversation history]
```

---

## 7. 安全设计

### 7.1 认证与授权

- **设备认证**：使用 JWT Token，设备连接时验证
- **配对验证**：6 位随机配对码，5 分钟有效期
- **消息签名**：关键消息使用 HMAC 签名

### 7.2 消息安全

- **传输加密**：所有通信使用 TLS/WSS
- **敏感信息**：配对码、Token 不在日志中明文记录
- **消息过滤**：禁止发送敏感配置信息

### 7.3 访问控制

```
┌─────────────────┐
│   Telegram Bot  │
│   (入口限制)     │
└────────┬────────┘
         │ 仅处理已配对用户
         ▼
┌─────────────────┐
│   API Server    │
│   (Token 验证)  │
└────────┬────────┘
         │ 设备验证
         ▼
┌─────────────────┐
│   Gateway       │
│   (本地执行)     │
└─────────────────┘
```

### 7.4 安全建议

- **DM 政策**：默认仅处理已配对用户的 DM
- **命令白名单**：可配置允许的 Shell 命令
- **超时限制**：单次命令执行最大时长 5 分钟
- **配额限制**：每小时最多消息数（可配置）

---

## 8. 部署方案

### 8.1 云端服务部署

#### 8.1.1 Docker Compose 部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: claude_gateway
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  api:
    build: ./api
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://user:password@postgres:5432/claude_gateway
      REDIS_URL: redis://redis:6379
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      - postgres
      - redis

  websocket:
    build: ./websocket
    ports:
      - "3001:3001"
    environment:
      REDIS_URL: redis://redis:6379
    depends_on:
      - redis

volumes:
  postgres_data:
  redis_data:
```

#### 8.1.2 环境变量

```bash
# .env
TELEGRAM_BOT_TOKEN=xxx
JWT_SECRET=your-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/claude_gateway
REDIS_URL=redis://localhost:6379
API_PORT=3000
WS_PORT=3001
```

### 8.2 本地客户端部署

#### 8.2.1 macOS (LaunchD)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claudegateway.client</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cc-claw</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

#### 8.2.2 Linux (Systemd)

```ini
[Unit]
Description=CC-Claw Client
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/cc-claw start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 9. 客户端设计

### 9.1 客户端架构

```
┌─────────────────────────────────────────────────┐
│              Gateway Client                      │
├─────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  WebSocket  │  │   Message   │  │  Claude │ │
│  │   Manager   │──│   Handler   │──│   CLI   │ │
│  └─────────────┘  └─────────────┘  └─────────┘ │
│         │                 │             │       │
│         └─────────────────┴─────────────┘       │
│                       │                          │
│                 ┌─────▼─────┐                    │
│                 │  Tools   │                    │
│                 │ Manager  │                    │
│                 └──────────┘                    │
└─────────────────────────────────────────────────┘
```

### 9.2 客户端核心模块

#### 9.2.1 配置管理

```python
# config.py
class Config:
    def __init__(self):
        self.server_url = "wss://your-server.com"
        self.device_token = None
        self.auto_reconnect = True
        self.reconnect_delay = 5
        self.claude_path = "claude"  # 或完整路径
        self.timeout = 300  # 5分钟
```

#### 9.2.2 WebSocket 管理

```python
# websocket_manager.py
class WebSocketManager:
    def __init__(self, config: Config):
        self.ws = None
        self.config = config
        self.message_handlers = []

    async def connect(self):
        # 建立 WebSocket 连接
        # 处理认证
        # 启动心跳

    async def send(self, message: dict):
        # 发送消息

    async def reconnect(self):
        # 重连逻辑
```

#### 9.2.3 Claude CLI 调用

```python
# claude_executor.py
class ClaudeExecutor:
    def __init__(self, config: Config):
        self.config = config

    async def execute(self, prompt: str, context: dict = None) -> str:
        # 构建命令
        cmd = [self.config.claude_path, "-p", prompt]

        # 执行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout
        )

        return result.stdout or result.stderr
```

### 9.3 CLI 命令

```
cc-claw start      # 启动守护进程
cc-claw stop       # 停止守护进程
cc-claw status     # 查看状态
cc-claw pair       # 开始配对
cc-claw unpair     # 解除配对
cc-claw config     # 查看/修改配置
cc-claw logs       # 查看日志
```

---

## 10. 扩展性考虑

### 10.1 多平台支持

未来可扩展支持更多消息平台：

- Discord
- Slack
- WhatsApp
- Line
- 微信（需要逆向）

### 10.2 集群部署

```
                    ┌─────────────┐
                    │   Load      │
                    │   Balancer  │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Server 1   │    │  Server 2   │    │  Server N   │
│  (WS+API)    │    │  (WS+API)    │    │  (WS+API)    │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                    ┌─────▼─────┐
                    │   Redis   │
                    │  Cluster  │
                    └───────────┘
```

### 10.3 消息分片

Claude CLI 输出可能很长，需要分片发送：

```python
def split_message(text: str, max_length: int = 4000) -> List[str]:
    chunks = []
    for i in range(0, len(text), max_length):
        chunks.append(text[i:i + max_length])
    return chunks
```

---

## 11. 开发计划

### 11.1 MVP (最小可行产品)

| 阶段 | 功能 | 预计时间 |
|------|------|----------|
| Phase 1 | 服务器搭建 + Telegram Bot 基础 | 2 天 |
| Phase 2 | WebSocket 连接 + 消息转发 | 2 天 |
| Phase 3 | 本地 Gateway 客户端 | 2 天 |
| Phase 4 | 配对机制 + 认证 | 1 天 |
| Phase 5 | 测试 + 修复 | 2 天 |

### 11.2 后续功能

- 语音消息支持
- 文件上传/下载
- 截屏功能
- 交互式消息（按钮等）
- 会话管理

---

## 12. 参考资料

- [OpenClaw 官方仓库](https://github.com/openclaw/openclaw)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Claude Code 官方文档](https://docs.anthropic.com/en/docs/claude-code/overview)

---

## 13. 附录

### 13.1 术语表

| 术语 | 定义 |
|------|------|
| Gateway | 网关服务，作为消息转发中枢 |
| Client/Gateway Client | 本地运行的客户端程序 |
| Pairing | 配对，将 Telegram 用户与设备绑定 |
| Device Token | 设备认证令牌 |

### 13.2 配置示例

```json
{
  "server": {
    "api_url": "https://api.cc-claw.com",
    "ws_url": "wss://ws.cc-claw.com"
  },
  "client": {
    "auto_start": true,
    "reconnect": true,
    "claude_path": "claude",
    "timeout": 300
  },
  "security": {
    "allowed_commands": ["*"],
    "max_message_length": 10000
  }
}
```
