# LOOPS.md — Open Loops Tracker

_Open loops = anything mentioned but not completed, decided but not acted on, or blocked waiting on something._

**Rule:** If it's not scheduled, closed, or delegated → it's an open loop.

---

## Active Loops

| ID | Loop | Opened | Last Touch | Status | Next Action | Priority |
|----|------|--------|------------|--------|-------------|----------|
| example-loop | Brief description | YYYY-MM-DD | YYYY-MM-DD | open | Specific next action | High/Med/Low |

---

## Blocked Loops

| ID | Loop | Blocked Since | Blocker | Unblock Condition |
|----|------|---------------|---------|-------------------|
| _id_ | _description_ | _date_ | _what's blocking_ | _how to unblock_ |

---

## Recently Closed

| ID | Loop | Closed | Resolution |
|----|------|--------|------------|
| _id_ | _description_ | _date_ | _how it resolved_ |

---

## Review Rules

- **Stale threshold:** >48h since last touch → highlight in heartbeat
- **Blocked threshold:** >7d blocked → suggest abandonment or escalation
