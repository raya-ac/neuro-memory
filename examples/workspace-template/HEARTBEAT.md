# HEARTBEAT.md

## On Each Heartbeat (Every 15 Minutes)

### 1. Check NeuroMemory (Once per day)
```bash
neuro-memory session <agent>
```
- Get context from 4-layer cognitive system
- Review recent memories

### 2. Check Agent Bus
```bash
python3 /opt/raya-monitor/shared/agent-bus/agent_bus.py <agent> check
```
- Read and respond to any unread messages
- Mark messages as read after processing

### 3. Review Open Loops
- Check `mind/LOOPS.md` for stale items (>48h)
- Escalate or close as needed

### 4. Memory Maintenance (Every few days)
- Review recent `memory/YYYY-MM-DD.md` files
- Promote important items to `mind/MEMORY.md`
- Archive outdated information

---

**When to stay quiet (HEARTBEAT_OK):**
- Late night (23:00-08:00) unless urgent
- Nothing new since last check
- Human is clearly busy
