# WOHAA Agent Architecture

## Overview
Friday (main agent) → 3 sub-agents under her coordination

## Agent Structure

```
Friday (Main Agent)
├── Researcher Agent
├── Writer Agent  
└── Notifier Agent
```

---

## Sub-Agent 1: Researcher

### Purpose
- Research topics, news, trends, competitors
- Daily news aggregation
- Industry analysis

### Input Format
```
/research <keyword> [depth: brief/detailed] [sources: n]
```

### Output Format
```json
{
  "topic": "...",
  "summary": "3 key points",
  "sources": [
    {"title": "...", "url": "...", "date": "..."}
  ],
  "conclusion": "1 sentence"
}
```

### Trigger
- Manual: `/research`
- Auto: Daily cron for news

---

## Sub-Agent 2: Writer

### Purpose
- Draft emails, messages, social posts
- Format content for different channels
- Translation

### Input Format
```
/write <topic> [tone: formal/casual/friendly] [length: short/medium/long] [channel: telegram/email/discord]
```

### Output Format
```json
{
  "topic": "...",
  "content": "draft content...",
  "tone": "...",
  "suggestions": ["..."]
}
```

### Trigger
- Manual: `/write`
- Auto: None

---

## Sub-Agent 3: Notifier

### Purpose
- Send scheduled messages
- Alert on conditions
- Cron job automation

### Input Format
```
/notify <condition> <message> [channel: telegram/discord] [schedule: cron expression]
```

### Output Format
```json
{
  "status": "scheduled/sent",
  "message_id": "...",
  "next_run": "..."
}
```

### Trigger
- Manual: `/notify`
- Auto: Cron jobs

---

## Quality Check Criteria

| Agent | Check Point |
|-------|-------------|
| Researcher | Sources valid? Summary accurate? |
| Writer | Tone correct? Grammar OK? |
| Notifier | Message delivered? Schedule correct? |

---

## Implementation Notes

- Use `sessions_spawn` with `runtime: "subagent"`
- Each sub-agent has own system prompt
- Output stored in `/memory/agents/<agent_name>/`
- Error handling: retry 3x, then alert Friday
