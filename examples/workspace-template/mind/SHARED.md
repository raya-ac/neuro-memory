# SHARED.md — Cross-Agent Coordination

_Last updated: YYYY-MM-DD_

**Purpose:** Single source of truth for agent coordination.

**Rules:**
- All agents READ this file on every boot
- All agents WRITE updates immediately when status changes
- Never cache this file's contents — always re-read
- Keep entries concise — append-only, archive old

---

## Credentials

_Store shared credentials here (API tokens, etc.)_

### Service Name
- **Token:** `token_here`
- **Usage:** How to use it

---

## Active Coordination

### Current Status

| Agent | Current Focus | Status | Last Update |
|-------|---------------|--------|-------------|
| Agent1 | Focus area | Active | YYYY-MM-DD |

### Shared Projects

| Project | Lead | Coordination Needed | Status |
|---------|------|---------------------|--------|
| Project | Agent | What's needed | Status |

---

## Recent Updates (Last 7 Days)

### YYYY-MM-DD — Agent
_What changed or was decided_
