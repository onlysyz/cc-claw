# GitHub Trending Optimization Guide

## How to Get on GitHub Trending

### 1. Repository Setup Checklist

- ✅ Great README with demo GIF
- ✅ Clear one-liner description in repo description
- ✅ Topics/tags set (ai, claude-code, automation, python, productivity)
- ✅ Releases with changelog
- ✅ Contributing guidelines
- ✅ Code of conduct
- ✅ License file
- ✅ Stars accumulating (need 100+ for trending consideration)

### 2. README Trending Version (One-liner you can copy)

**Repo Description:**
```
🦞 CC-Claw — Your tireless AI working companion. Make every Claude Code token count 24/7.
```

### 3. Topics to Set

Go to repo Settings → Topics:
```
ai claude-code automation productivity python telegram-bot
autonomous-ai developer-tools workflow bot lark-api
```

### 4. Release Checklist

```bash
# Create initial release
git tag -a v1.0.0 -m "Initial release - autonomous AI working companion"
git push origin v1.0.0

# Create GitHub release via UI with:
# - Title: v1.0.0 - Initial Release
# - Description: What's new
# - Binary: None (pure Python)
```

### 5. GitHub Actions for Trending Boost

Add `.github/star.yml` to auto-star:

```yaml
name: Auto-star
on:
  push:
    branches: [main]

jobs:
  star:
    runs-on: ubuntu-latest
    steps:
      - uses: actions-cool/github-auto-star@v1
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
```

### 6. Social Proof Strategy

**Day 1-3:** Share on:
- Twitter/X (tag @cc_claw)
- Hacker News (Show HN)
- Reddit r/programming
- Dev.to
- LinkedIn

**Week 1:** Post updates:
- "100 stars!" celebration post
- "How it works" technical deep-dive
- User testimonials if available

### 7. README Badges to Add

```markdown
[![Stars](https://img.shields.io/github/stars/onlysyz/cc-claw?style=social)](https://github.com/onlysyz/cc-claw/stargazers)
[![Forks](https://img.shields.io/github/forks/onlysyz/cc-claw?style=social)](https://github.com/onlysyz/cc-claw/network/members)
[![Issues](https://img.shields.io/github/issues/onlysyz/cc-claw)](https://github.com/onlysyz/cc-claw/issues)
[![License](https://img.shields.io/github/license/onlysyz/cc-claw)](LICENSE)
```

### 8. Pitch for GitHub Explore Newsletter

Email: opensource@github.com

Subject: CC-Claw — Autonomous AI working companion for Claude Code

```
CC-Claw is an open-source autonomous AI working companion that transforms Claude Code tokens into 24/7 continuous work.

Key features:
- Goal-driven autonomous loop
- Smart throttling (saves tokens on 429)
- Built-in tools for file processing, web scraping, process management
- 100% local execution

We think it would be a great fit for GitHub Explore given the interest in AI developer tools.

Repo: https://github.com/onlysyz/cc-claw
Demo: https://cc-claw.dev/demo
```

### 9. Alternative Tools Submission

Submit to:
- [Alternative.to](https://alternative.to/) - "Alternative to Claude Code plans waste"
- [SaaSHub](https://www.saashub.com/) - CC-Claw listing
- [Product Hunt](https://www.producthunt.com/) - Already prepared

### 10. README Animation Tip

Add this to README.md header for dynamic effect:

```markdown
<p align="center">
  <img src="https://raw.githubusercontent.com/onlysyz/cc-claw/main/demo/cc-claw-preview.svg" width="600"/>
</p>
```

---

## Quick Launch Checklist

| Task | Status | Notes |
|------|--------|-------|
| Set repo description | ⬜ | "Your tireless AI working companion" |
| Add topics | ⬜ | ai, claude-code, automation, etc. |
| Create v1.0.0 release | ⬜ | With changelog |
| Submit to Product Hunt | ⬜ | Use PRODUCT_HUNT.md |
| Post Show HN | ⬜ | Use HACKER_NEWS.md |
| Publish Dev.to article | ⬜ | Use DEV_TO.md |
| Publish 掘金 article | ⬜ | Use JUEJIN.md |
| Tweet announcement | ⬜ | Tag @cc_claw |
| Email GitHub Explore | ⬜ | Use pitch above |
| Monitor and reply | ⬜ | Respond within 2 hours |
