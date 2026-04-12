# CC-Claw Community Onboarding

## Welcome Message (Auto-send on Join)

```
👋 Welcome to CC-Claw Community!

I'm excited you're here! 🎉

**What is CC-Claw?**
CC-Claw is your tireless AI working companion. It makes your Claude Code
tokens work 24/7 — setting goals, breaking tasks, executing, and never
wasting tokens on rate limits.

**Quick Links:**
- 📖 Docs: github.com/onlysyz/cc-claw/wiki
- 🐛 Issues: github.com/onlysyz/cc-claw/issues
- 💬 Discussions: github.com/onlysyz/cc-claw/discussions

**How to Get Started:**
1. ⭐ Star us on GitHub
2. 📥 Install: `pip install -e . && cc-claw install`
3. 🤖 Set up Telegram bot (instructions in docs)
4. 🎯 Send /start to set your first goal

**Have questions?**
- 🤖 #support — General help
- 📖 #docs — Documentation questions
- 💡 #ideas — Suggest features

**Community Guidelines:**
👉 Read #📜rules

Can't wait to see what you build! 🦞
```

---

## New Member Checklist

```
✅ Complete these to get started:

1. ⭐ Star the repo
   github.com/onlysyz/cc-claw

2. 📥 Install CC-Claw
   pip install -e . && cc-claw install

3. 👋 Introduce yourself
   Post in #💬general — What are you working on?

4. 🐛 Try it out
   Set a small goal and see what happens

5. 💡 Share feedback
   We read every piece of feedback!
```

---

## Role Assignment

### Automatic Roles

| Role | Criteria | Color |
|------|----------|-------|
| @member | Everyone | Default |
| @contributor | 1+ PR merged | Green |
| @early-adopter | Joined first month | Blue |
| @power-user | Active 3+ months | Purple |

### Self-Assign Roles

Access via #🎨showcase:
- 🐛 Bug Reporter — Reported 3+ bugs
- 💡 Feature Requester — 5+ ideas
- 📖 Helper — 10+ helpful answers

### How to Get Roles

```
# To get @contributor:
1. Submit a PR to github.com/onlysyz/cc-claw
2. Get it merged!
3. We'll add the role automatically

# To get @early-adopter:
1. Join in the first month after launch
2. We'll add it automatically

# To get @power-user:
1. Be active for 3+ months
2. Help others in the community
3. We'll notice! 😄
```

---

## Contributor Guide

### Ways to Contribute

1. **Code** — Fix bugs, add features
2. **Docs** — Improve documentation
3. **Issues** — Report bugs, suggest features
4. **Support** — Help other users
5. **Content** — Write tutorials, make videos
6. **Feedback** — Give product feedback

### Quick Start (Code)

```bash
# 1. Fork the repo
# Click "Fork" on github.com/onlysyz/cc-claw

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/cc-claw.git
cd cc-claw

# 3. Create a branch
git checkout -b feature/your-feature-name

# 4. Make your changes
# Edit files...

# 5. Test
python -m pytest tests/

# 6. Commit
git commit -m "Add: your feature description"

# 7. Push
git push origin feature/your-feature-name

# 8. Open a PR
# Go to github.com/onlysyz/cc-claw and click "Compare & pull request"
```

### Code Style

```python
# Use PEP 8
# 4 spaces for indentation
# Max line length: 100
# Use type hints where possible

def example_function(param: str, count: int = 10) -> list:
    """Example docstring.

    Args:
        param: Description of param.
        count: Number of items. Default 10.

    Returns:
        List of items.
    """
    return [param] * count
```

### PR Template

```markdown
## Summary
[Short description of what this PR does]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
[ ] Tests added
[ ] Tests passed
[ ] Manual testing done

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated (if needed)

## Screenshots (if UI change)
[Add screenshots here]
```

---

## FAQ for New Members

**Q: Is CC-Claw free?**
A: Yes, the core product is MIT licensed and free. PRO/ENTERPRISE tiers will have paid features in the future.

**Q: Do I need Claude Code?**
A: Yes, CC-Claw wraps Claude Code CLI. You need a Claude Code plan to use it.

**Q: How is this different from AutoGPT?**
A: AutoGPT is general-purpose. CC-Claw specifically wraps Claude Code for persistent, goal-driven work with smart token management.

**Q: Where does code execute?**
A: On YOUR machine. CC-Claw cloud only handles orchestration (messages, scheduling). Your code never leaves your device.

**Q: How do I get help with an error?**
A: Post in #🤖support with: OS, Claude version, error logs, and steps to reproduce.

**Q: How can I contribute?**
A: See the Contributor Guide above! Code, docs, bug reports, and feature requests all help.

**Q: Will you add support for X?**
A: Maybe! Post in #💡ideas with your use case.

---

## Recognition

### Contributors Hall of Fame

Monthly shoutouts for top contributors:

```
🏆 Top Contributors — [Month Year]

Code: @username
Documentation: @username
Support: @username
Ideas: @username

Thank you all! 🙌
```

### Swag Program

Coming soon:
- Stickers for contributors
- T-shirts for top contributors
- Special Discord badge for repeat contributors

---

## Moderation

### Warning System

1. **First warning** — Verbal reminder in channel
2. **Second warning** — DM with explanation
3. **Mute** — 24 hours (for spam/repeated issues)
4. **Ban** — For serious violations

### What Gets You Banned

- Hate speech or harassment
- Spam (repeated promotional messages)
- NSFW content
- Impersonation
- Sharing exploits or malicious content

### Appeal Process

If banned, you can appeal by:
1. Emailing support@cc-claw.dev
2. Explaining what happened
3. Promising to follow rules

We review appeals within 7 days.

---

## Emergency Contacts

| Situation | Contact |
|-----------|---------|
| Security vulnerability | security@cc-claw.dev |
| Urgent bug affecting users | DM @onlysyz |
| Moderation issue | DM @moderator |
| Partnership inquiry | partnerships@cc-claw.dev |
