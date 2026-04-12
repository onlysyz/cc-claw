# CC-Claw Feedback Collection System

## Feedback Channels

| Channel | Type | Response SLA |
|---------|------|--------------|
| #bug-reports | Bug reports | 24 hours (confirmed), 1 week (fix) |
| #feature-requests | Ideas | 48 hours (review), monthly (decision) |
| #support | Help requests | 4 hours (business hours) |
| #showcase | Success stories | 48 hours (engagement) |
| Contact form | Anonymous | 72 hours |

---

## GitHub Issues Integration

### Auto-Label Bot Setup

Labels to create:
- `bug` - Bug reports
- `enhancement` - Feature requests
- `question` - Help questions
- `documentation` - Doc improvements
- `good-first-issue` - Beginner friendly
- `priority:high` - Critical issues
- `priority:medium` - Normal priority
- `priority:low` - Nice to have

### Issue Templates

#### Bug Report Template
```markdown
---
name: Bug Report
about: Report a bug in CC-Claw
title: '[BUG] '
labels: bug
assignees: onlysyz
---

## Bug Description
[Clear description of the bug]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [Third step]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- OS: [e.g., macOS 14.0]
- Claude Code version: [e.g., 1.0.42]
- CC-Claw version: [e.g., 1.0.0]

## Logs
```
[paste relevant logs here]
```

## Severity
- [ ] 🟢 Minor (cosmetic issue)
- [ ] 🟡 Medium (workaround exists)
- [ ] 🔴 Critical (blocks all usage)

## Additional Context
[Anything else that might be relevant]
```

#### Feature Request Template
```markdown
---
name: Feature Request
about: Suggest a new feature for CC-Claw
title: '[FEATURE] '
labels: enhancement
assignees: onlysyz
---

## Problem Statement
[Describe the problem this feature would solve]

## Proposed Solution
[Describe what you want to happen]

## Use Cases
[Who would use this and when?]

## Alternatives Considered
[What other approaches did you consider?]

## Additional Context
[Screenshots, mockups, or examples]
```

---

## Monthly Feedback Review

### First Week of Each Month: Triage

**Process:**
1. Collect all feedback from previous month
2. Categorize: Bugs, Features, Questions, Praise
3. Identify patterns (3+ users = common)
4. Prioritize: Critical → High → Medium → Low

**Feedback Triage Sheet:**

| Date | Source | Type | Description | Count | Priority | Status |
|------|--------|------|-------------|-------|----------|--------|
| Jan 5 | Discord | Bug | Token tracking inaccurate | 5 | High | Fix in v1.1 |
| Jan 8 | GitHub | Feature | Docker tool | 3 | Medium | Backlog |
| Jan 12 | Twitter | Praise | Saved 2hrs/week | 1 | N/A | Social proof |

### Second Week: Decision

**Review Meeting Agenda (30 min):**

```
1. Review critical/high priority bugs (10 min)
2. Review top feature requests (10 min)
3. Decide what goes in next release (10 min)
```

**Output: Release Planning Document**

```markdown
## CC-Claw v1.X Release Plan

### Bugs to Fix
- [ ] #123: Token tracking fix
- [ ] #124: WebSocket reconnect

### Features to Add
- [ ] #125: Docker tool
- [ ] #126: Scheduled reminders

### Won't Fix (v1.X)
- [ ] #127: Feature requested only once, low impact
```

---

## User Feedback Surveys

### Monthly Pulse Survey

**Questions:**

1. How satisfied are you with CC-Claw? (1-5)
2. How likely to recommend to a friend? (0-10 NPS)
3. What's the #1 thing CC-Claw helps you with?
4. What's the biggest pain point?
5. What feature would make CC-Claw 10x better?

**Distribution:**
- Send via Discord announcement
- Google Form or Typeform
- Incentive: Feature request flair

### Quarterly Deep Survey

**Questions:**

1. How often do you use CC-Claw?
   - Daily / Weekly / Monthly / Rarely

2. What do you primarily use CC-Claw for?
   - Bug fixes / Feature development / DevOps / Documentation / Other

3. How does CC-Claw compare to manual work?
   - Much faster / Faster / Same / Slower / Much slower

4. What's your monthly token spend?
   - $0 / $1-20 / $21-50 / $51-100 / $100+

5. Would you pay for PRO tier?
   - Yes, already / Yes, if price was X / Maybe / No

6. Open feedback:
   [Text field]

---

## Feedback Response Templates

### Bug Confirmation
```
👋 Hey @user, thanks for the bug report!

I've confirmed this is a bug and it's now tracked as #issue_number.

Priority: [High/Medium/Low]
ETA: [This release / Next release / Backlog]

Thanks for helping make CC-Claw better! 🦞
```

### Feature Acknowledgment
```
💡 Thanks for this feature request!

I've added it to our tracking as #issue_number.

This would help because: [restate the value]
We'll review this in our monthly planning.

Want to help implement it? Let me know! 🙌
```

### Fix Released
```
✅ Hey everyone, [bug description] has been fixed in v[new_version]!

Update with:
pip install --upgrade cc-claw

Changelog: github.com/onlysyz/cc-claw/releases
```

---

## Feedback Metrics Dashboard

### Track Weekly

```
Community Health Metrics:
- Discord members: [count]
- Messages/week: [count]
- Support response time: [avg hours]
- Bug reports: [count]
- Feature requests: [count]

GitHub Metrics:
- Stars: [count]
- Forks: [count]
- Issues opened: [count]
- Issues closed: [count]
- PRs merged: [count]

Product Metrics:
- Active users: [estimate]
- Goals completed: [count]
- Tokens saved: [estimate]
```

---

## Feedback Channels Collection

### Auto-Collect From

| Source | Method | Frequency |
|--------|--------|-----------|
| Discord | Channel messages | Real-time |
| GitHub Issues | API | Real-time |
| Twitter DMs | Manual check | Daily |
| Email | Filter + label | Daily |
| Product Hunt | Dashboard | Weekly |

### Centralize in Notion/Airtable

```
Feedback Database:
- ID
- Date
- Source (Discord/GitHub/Twitter/Email)
- Type (Bug/Feature/Praise/Question)
- Description
- User (anonymous or handle)
- Status (New/Triaged/In Progress/Resolved)
- Version
- Priority
```

---

## Closing the Loop

### Monthly Community Update

Post in #announcements and GitHub Discussions:

```
## Monthly Update — [Month Year]

### 🐛 Bugs Fixed
- [Bug 1] — [1 sentence description]
- [Bug 2] — [1 sentence description]

### ✨ New Features
- [Feature 1] — [1 sentence description]
- [Feature 2] — [1 sentence description]

### 📊 Community Stats
- Members: [X] (+Y this month)
- GitHub Stars: [X] (+Y this month)
- Issues resolved: [X]/[Y]

### 💡 Top Feature Requests
- [Feature 1] — [X] votes
- [Feature 2] — [X] votes
- We're working on [top one]!

### 🙏 Thank You
Shoutout to @user1, @user2 for contributions!

### 📅 Next Month
- [Preview of what's coming]

Full changelog: github.com/onlysyz/cc-claw/releases
```
