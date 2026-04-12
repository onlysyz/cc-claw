# Hacker News Submission — CC-Claw

## Title Options (pick one)

1. **Show HN: CC-Claw – Make your Claude Code tokens work 24/7 autonomously** (recommended)
2. **CC-Claw: An autonomous AI working companion that never wastes your tokens**
3. **I built an AI that works while I sleep using my Claude Code plan**

---

## Post Content (for text submission)

```
Title: Show HN: CC-Claw – Make your Claude Code tokens work 24/7 autonomously

---

CC-Claw is an autonomous AI working companion that turns idle Claude Code tokens into continuous progress toward your goals.

**The problem I solved:**

I was spending $100/month on a Claude Code plan. But tokens sat idle 90% of the time. Chat, wait, copy-paste, repeat. Manual workflow that burned tokens on retries when hitting rate limits.

**What CC-Claw does:**

1. Set a goal via Telegram or Lark bot
2. AI decomposes it into actionable tasks
3. Claude Code executes tasks on YOUR machine (not cloud)
4. Smart throttling: stops on 429, checks hourly, resumes when tokens refresh

**Key features:**

- Goal-driven autonomous loop (task → execute → next → repeat)
- Priority queue: your urgent commands jump to front
- Silent mode: no periodic check-ins, reports only when you ask
- Built-in tools: FileProcessor, DataScraper, ApiClient, ProcessManager, GitHelper, DockerHelper
- 100% local execution — your code, your machine

**Architecture:**

You (Telegram/Lark) → CC-Claw Cloud → Your Device → Claude Code CLI

**If you want to try it:**

GitHub: https://github.com/onlysyz/cc-claw

Live demo page: https://cc-claw.dev/demo

Would love feedback from the HN community. What would make this more useful?

---

**AMA — Ask me anything about the build.**
```

---

## Ask HN Questions to Preempt

| Question | Answer |
|----------|--------|
| "Is this safe? Code runs locally?" | Yes, 100% local. Claude Code CLI executes on your machine. Cloud only handles orchestration. |
| "What happens on rate limit?" | Smart backoff: stops, waits 5min, checks hourly for token refresh, resumes. No wasted tokens. |
| "Why not use Claude API directly?" | CC-Claw uses Claude Code CLI which has full codebase context and tool access. More powerful for complex tasks. |
| "How is this different from Cursor/others?" | CC-Claw is the autonomous wrapper around Claude Code for continuous goal-oriented work, not a chat replacement. |

---

## Tips for HN Success

1. **Post timing:** Tuesday-Thursday, 6-9am PT (when HN traffic peaks)
2. **Engage comments immediately** in first 2 hours
3. **Share real numbers:** "saved $X in tokens", "completed Y tasks"
4. **Be honest about limitations**
5. **Reply to every comment** in first 3 hours
