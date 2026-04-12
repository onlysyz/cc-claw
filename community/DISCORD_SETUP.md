# CC-Claw Discord Community Setup Guide

## Discord Server Structure

### Server Overview

```
CC-Claw Community
├── 📜 rules              (Server rules)
├── 🎉 welcome            (Welcome channel)
├── 📢 announcements     (Official updates - @everyone)
├── 💬 general            (General discussion)
├── 🤖 support            (Help & troubleshooting)
├── 💡 ideas              (Feature requests & suggestions)
├── 🐛 bugs               (Bug reports)
├── 📖 docs               (Documentation help)
├── 🎨 showcase           (Show off what you built)
└── 🔧 dev-logs           (Development updates)
```

### Category: PUBLIC

#### 📜 rules
```
Welcome to CC-Claw Community! 🎉

Please follow these rules:

1. **Be Respectful**
   - Treat everyone with respect
   - No harassment, hate speech, or personal attacks

2. **Stay on Topic**
   - Keep discussions relevant to CC-Claw or AI agents
   - Use appropriate channels for different topics

3. **No Spam**
   - No unsolicited promotions
   - No repetitive messages
   - No self-promotion without permission

4. **Help Each Other**
   - Share your knowledge
   - Be patient with newcomers

5. **Bug Reports**
   - Use the #🐛bugs channel
   - Include: OS, Claude version, error logs, steps to reproduce

6. **Feature Requests**
   - Use #💡ideas channel
   - Describe the use case, not just the solution

7. **No NSFW Content**
   - Keep everything PG-13

Violation = warning → mute → ban (at moderator discretion)
```

#### 🎉 welcome
```
👋 Welcome to CC-Claw Community!

🦞 CC-Claw is your tireless AI working companion — making every token count.

**Quick Links:**
- 📖 Docs: github.com/onlysyz/cc-claw/wiki
- 🐛 Issues: github.com/onlysyz/cc-claw/issues
- 💬 Discussions: github.com/onlysyz/cc-claw/discussions

**Getting Started:**
1. ⭐ Star us on GitHub
2. 📥 Install: `pip install -e . && cc-claw install`
3. 🤖 Message the Telegram bot with /start

**Need Help?**
- 🤖 support — General troubleshooting
- 📖 docs — Documentation questions
- 💡 ideas — Suggest new features

**Community Guidelines:**
👉 Read #📜rules

We're glad you're here! 🎉
```

#### 📢 announcements
```
📢 Official Announcements

This channel is for:
- New releases & version updates
- Important security patches
- Community events
- Major feature announcements

Only admins can post here.
```

#### 💬 general
```
💬 General Chat

Talk about:
- CC-Claw tips & tricks
- AI agents & automation
- Your projects
- Industry news

Be helpful, be kind! 🙌
```

### Category: SUPPORT

#### 🤖 support
```
🤖 Support Channel

Need help with CC-Claw? We're here!

**Before asking:**
1. Check the docs: github.com/onlysyz/cc-claw/wiki
2. Search existing messages
3. Check #🐛bugs for known issues

**When asking:**
- Describe your issue clearly
- Include your OS and Claude version
- Paste error logs (use code blocks)
- Describe what you tried

**Format:**
```
OS: [e.g., macOS 14.0]
Claude: [version]
Issue: [describe]
Error: [paste error]
Steps: [1, 2, 3...]
```
```

#### 📖 docs
```
📖 Documentation Help

Questions about:
- Installation
- Configuration
- Usage
- API reference

We'll help you find what you need!
```

### Category: FEEDBACK

#### 💡 ideas
```
💡 Feature Requests

Have an idea? We'd love to hear it!

**Before posting:**
- Search if someone already suggested it
- Think about the use case, not just the solution

**Good request format:**
```
Feature: [short title]
Use case: [when would you use this?]
Why: [why is this important?]
```

Example:
```
Feature: Scheduled task reminders
Use case: I want CC-Claw to remind me of deadlines
Why: I work better with periodic check-ins
```
```

#### 🐛 bugs
```
🐛 Bug Reports

Found a bug? Let's fix it!

**Required info:**
1. OS + version
2. Claude Code version
3. CC-Claw version (`cc-claw --version`)
4. Steps to reproduce
5. Error logs (full logs, not just the last line)
6. Expected vs actual behavior

**Format:**
```markdown
## Bug Report

**Environment:**
- OS:
- Claude:
- CC-Claw:

**Steps to Reproduce:**
1.
2.
3.

**Expected:**
**Actual:**
**Logs:**
```
[paste logs here]
```

**Severity:**
- 🟢 Minor (cosmetic)
- 🟡 Medium (workaround exists)
- 🔴 Critical (blocks usage)
```
```

#### 🎨 showcase
```
🎨 Showcase

Built something cool with CC-Claw? Show it off!

- Screenshots
- Workflow demos
- Integrations
- Blog posts about CC-Claw

Let's see what you've made! 🚀
```

### Category: DEV

#### 🔧 dev-logs
```
🔧 Development Updates

Behind-the-scenes updates from the CC-Claw team.

- New features in progress
- Technical deep dives
- Architecture decisions
- Community stats

Posted monthly (or when major things happen)!
```

---

## Bot Setup

### MEE6 Bot (Moderation + Welcome)

```
!setup
→ Welcome message: enabled
→ Welcome channel: #🎉welcome
→ Welcome message: "Welcome {user} to CC-Claw Community! 🎉"
```

### Carl-bot (Reaction Roles)

```
Reaction Roles:
- 🐛 Bug Reporter (green bug emoji)
- 💡 Feature Requester (lightbulb emoji)
- 📖 Contributor (book emoji)
```

### Discord Timestamps

Use for events:
```
Tuesday, January 14 at 6:00 PM UTC
```

---

## Moderation Team

| Role | Responsibilities |
|------|-----------------|
| @Owner | Full access, announcements |
| @Admin | Manage channels, enforce rules |
| @Moderator | Review bugs/ideas, help users |
| @Contributor | Help with docs, marked in Discord |

---

## Discord Server Invite Link

Create invite (expires in 7 days):
```
https://discord.gg/new?reason=cc-claw-community
```

Permanent link after server setup:
```
https://discord.gg/cc-claw
```
