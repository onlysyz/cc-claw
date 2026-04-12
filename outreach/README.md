# CC-Claw Outreach — Open Source AI Agent Projects

Outreach messages for partnering with or integrating into popular open source AI agent projects.

---

## Target Projects

| # | Project | GitHub | Focus | Contact |
|---|---------|--------|-------|---------|
| 1 | **AutoGPT** | @SignificantGravitas/AutoGPT | Autonomous general-purpose AI agent | Discord / GitHub Issues |
| 2 | **LangChain** | @langchain-ai/langchain | LLM framework with agents | Discord / GitHub |
| 3 | **AutoGen** | @microsoft/autogen | Multi-agent conversation framework | GitHub Discussions |
| 4 | **CrewAI** | @joaomdmoura/crewAI | Multi-agent orchestration | Discord / Twitter |
| 5 | **AgentGPT** | @ reworkd-agent/agentgpt | Web-based autonomous AI agent | Discord |
| 6 | **MetaGPT** | @/metagpt-ai/MetaGPT | Multi-agent software development | Discord |
| 7 | **ChatDev** | @open-chatgpt/ChatDev | Virtual software company agents | GitHub |
| 8 | **OpenDevin** | @/allenai/opendevin | Autonomous coding agent | Discord |
| 9 | **Superagent** | @ superagent-labs/superagent | Agent infrastructure | Discord / Twitter |
| 10 | **BeeAI** | @/@bee-ai/beeai | Autonomous agents with memory | Discord |
| 11 | **，短** | @ shortai/shortai | Cursor-like AI coding | GitHub |
| 12 | **Codeium** | @andex熠/Codeium | AI coding assistant | Twitter / Email |

---

## Email Template (Primary)

**Subject:** Partnership Opportunity — CC-Claw + [Project Name]

```
Hi [Name/Team],

I built CC-Claw (github.com/onlysyz/cc-claw) — an open source autonomous AI
working companion that wraps Claude Code in a continuous goal-driven loop.

I think CC-Claw could be valuable for [Project Name]'s users because:

• Continuous Execution: CC-Claw handles rate limits intelligently
  (429 → wait → check hourly → resume). No wasted tokens.

• Built-in Tools: FileProcessor, DataScraper, GitHelper, DockerHelper,
  ProcessManager — ready to use out of the box.

• Private: All execution happens locally. Your code, your machine.

• Smart Throttling: Saves ~$20/month in token costs per user by
  avoiding retry waste.

Would you be open to exploring a partnership? I'm thinking:

1. Integration: CC-Claw as a backend executor for [Project Name]
2. Co-marketing: Joint tutorial or comparison article
3. Feature cross-promotion: "Powered by CC-Claw" badge for compatible tools

I'd love to jump on a quick call to discuss. No commitment — just exploring.

Best,
[Your Name]
GitHub: github.com/onlysyz
Twitter: @cc_claw
```

---

## Discord Server Template

**For: AutoGPT, AgentGPT, CrewAI, AutoGen, Superagent, BeeAI, OpenDevin, MetaGPT**

```
👋 Hey everyone!

I'm the creator of CC-Claw (github.com/onlysyz/cc-claw) — an open source
autonomous AI working companion that makes Claude Code tokens work 24/7.

I built it to solve a problem: Claude Code tokens sit idle 90% of the time.
CC-Claw wraps it in a continuous goal-driven loop with smart throttling.

I noticed [Project Name] is doing similar work in the AI agent space, and
I'd love to explore how we could work together.

Possible ideas:
• Integration: CC-Claw as an execution backend
• Joint tutorial showing how to use both together
• Feature cross-reference ("works with CC-Claw")

Happy to jump on a call or just chat here. No agenda — genuinely interested
in connecting and seeing if there's mutual value.

GitHub: github.com/onlysyz/cc-claw
Demo: cc-claw.dev/demo
```

---

## GitHub Issue Template

**For: LangChain, AutoGen, ChatDev**

**Issue Title:** Partnership / Integration Proposal: CC-Claw as Execution Backend

```
## Proposal: CC-Claw Integration

### What is CC-Claw?

CC-Claw (github.com/onlysyz/cc-claw) is an open source autonomous AI
working companion that transforms Claude Code into a 24/7 goal-driven worker.

### Why This Could Help [Project Name] Users

1. **Token Efficiency**: Smart throttling saves ~$20/month in avoided retry waste
2. **Persistent Execution**: Users set a goal, CC-Claw works until it's done
3. **Built-in Tools**: FileProcessor, DataScraper, GitHelper, DockerHelper ready to use
4. **Local Execution**: All code stays on user's machine

### Proposed Integration

[Choose one:]

**Option A — Tool Integration**
Add CC-Claw as a tool provider in [Project Name]:

```python
from cc_claw import tools
# Use FileProcessor, DataScraper, etc.
```

**Option B — Backend Executor**
Replace direct LLM calls with CC-Claw for persistent goal execution:

```python
from cc_claw import Executor
executor = Executor(goal="Implement user auth system")
executor.run_until_complete()
```

**Option C — Documentation Cross-Reference**
Add CC-Claw to related projects list with "works well together" badge.

### Next Steps

Happy to:
• Write the integration code myself
• Help with documentation
• Create a joint tutorial
• Discuss on a call

GitHub: github.com/onlysyz/cc-claw
Demo: cc-claw.dev/demo
```

---

## Twitter DM Template (50-100 chars)

**For: Project founders on Twitter**

```
Hi [Name]! I built CC-Claw (github.com/onlysyz/cc-claw) — autonomous AI
working companion. Would love to explore how we could work together.
Open to chat?
```

---

## Personalized Messages by Project

### AutoGPT

```
Hey AutoGPT team!

CC-Claw (github.com/onlysyz/cc-claw) solves a problem I think AutoGPT
users face: tokens burn on retries when hitting rate limits.

CC-Claw has smart throttling built in — 429 → wait → check hourly →
resume automatically.

Would love to explore making CC-Claw an execution option for AutoGPT,
or at least cross-referencing as complementary tools.

Demo: cc-claw.dev/demo
```

### CrewAI

```
Hi CrewAI!

I built CC-Claw — an autonomous AI companion that could complement
CrewAI's multi-agent orchestration.

CC-Claw's built-in tools (FileProcessor, DataScraper, GitHelper,
DockerHelper) could be used by CrewAI agents out of the box.

Interested in a potential integration? Happy to write the code.

GitHub: github.com/onlysyz/cc-claw
```

### MetaGPT

```
Hey MetaGPT team!

Your multi-agent software development approach is impressive. CC-Claw
could serve as an execution layer — persistent goal-driven work with
smart throttling for long-running tasks.

Would love to discuss a potential integration where CC-Claw handles
the "run until complete" loop while MetaGPT handles the coordination.

Open to a call?
```

### LangChain

```
Hi LangChain team!

CC-Claw (github.com/onlysyz/cc-claw) adds persistent goal-driven
execution to any LLM workflow. Built-in tools + smart throttling.

I think CC-Claw could be valuable as:
1. A LangChain tool (CC-Claw Tool)
2. An agent backend for LangChain agents
3. Documentation cross-reference

Happy to contribute the integration code myself.

Demo: cc-claw.dev/demo
```

### OpenDevin

```
Hey OpenDevin team!

We're solving similar problems — autonomous coding agents. CC-Claw
focuses on making Claude Code work 24/7 with smart throttling.

I'd love to explore how we could:
1. Use OpenDevin as the reasoning layer + CC-Claw as executor
2. Cross-reference as complementary tools
3. Joint blog post about autonomous coding

Demo: cc-claw.dev/demo
```

---

## Outreach Tracking

| Project | Channel | Sent | Response | Status |
|---------|---------|------|----------|--------|
| AutoGPT | Discord | ⬜ | - | Pending |
| LangChain | GitHub | ⬜ | - | Pending |
| AutoGen | GitHub | ⬜ | - | Pending |
| CrewAI | Discord | ⬜ | - | Pending |
| AgentGPT | Discord | ⬜ | - | Pending |
| MetaGPT | Discord | ⬜ | - | Pending |
| ChatDev | GitHub | ⬜ | - | Pending |
| OpenDevin | Discord | ⬜ | - | Pending |
| Superagent | Discord | ⬜ | - | Pending |
| BeeAI | Discord | ⬜ | - | Pending |

---

## Best Practices

1. **Timing**: Post in Discord during business hours (9am-5pm PT Tue-Thu)
2. **Follow up**: If no response in 1 week, follow up once
3. **Add value first**: Don't just ask — show what CC-Claw brings
4. **Be flexible**: Let them decide the collaboration format
5. **Keep it short**: Discord DMs = 2-3 sentences + link

---

## Alternative: GitHub Discussions

For projects without active Discord:

1. Find their GitHub Discussions page
2. Post under "Ideas" or "Integrations"
3. Follow the template above
4. Engage with comments immediately
