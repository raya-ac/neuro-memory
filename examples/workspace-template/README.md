# Workspace Template

A complete agent workspace template for use with NeuroMemory.

## Quick Start

1. Copy this folder to create a new agent workspace:
   ```bash
   cp -r examples/workspace-template ~/.openclaw/workspace-myagent
   ```

2. Edit the files:
   - `SOUL.md` — Define your agent's personality
   - `IDENTITY.md` — Set name, emoji, avatar
   - `USER.md` — Fill in your human's details
   - `mind/MEMORY.md` — Start building long-term memory

3. Add to your OpenClaw config:
   ```json
   {
     "agents": {
       "list": [{
         "id": "myagent",
         "name": "MyAgent",
         "workspace": "/root/.openclaw/workspace-myagent"
       }]
     }
   }
   ```

## File Structure

```
workspace-template/
├── AGENTS.md          # Agent boot sequence and rules
├── SOUL.md            # Core personality and values
├── IDENTITY.md        # Name, emoji, avatar
├── USER.md            # Human context
├── TOOLS.md           # Environment-specific notes
├── HEARTBEAT.md       # Periodic task checklist
│
├── mind/              # Persistent cognition
│   ├── MEMORY.md      # Long-term curated memory
│   ├── PROFILE.md     # Human's cognitive profile
│   ├── PROJECTS.md    # Active projects
│   ├── GOALS.md       # Goal tracking
│   ├── DECISIONS.md   # Decision log
│   ├── ERRORS.md      # Anti-repeat patterns
│   ├── LOOPS.md       # Open loops tracker
│   ├── INBOX.md       # Quick capture
│   ├── SHARED.md      # Cross-agent coordination
│   ├── ROADMAP/       # Project roadmaps
│   ├── CONTEXT/       # Session snapshots
│   ├── TEMPLATES/     # Reusable templates
│   ├── logs/          # Archived logs
│   └── scripts/       # Automation scripts
│
└── memory/            # Daily logs
    └── YYYY-MM-DD.md  # Today's log (create daily)
```

## Session Boot Sequence

Every session, your agent should:

1. **Core Identity** — Read SOUL.md, IDENTITY.md, USER.md
2. **Context** — Read today's and yesterday's memory logs
3. **State** — Read LOOPS.md, INBOX.md, SHARED.md
4. **NeuroMemory** — Run `neuro-memory session <agent>`

This is automated in AGENTS.md.

## Customization

### Personality (SOUL.md)
Edit to define:
- Tone and speaking style
- Values and boundaries
- Humor and pet phrases

### Human Context (USER.md, PROFILE.md)
Fill in:
- Communication preferences
- Technical context
- What works / doesn't work

### Memory (mind/MEMORY.md)
Start with:
- Known patterns
- Important context
- Lessons learned

## NeuroMemory Integration

This template works with the NeuroMemory 4-layer cognitive system:

```bash
# At session start
neuro-memory session myagent

# Search memories
neuro-memory recall myagent "query"

# Check health
neuro-memory health

# Sync workspace files to memory
neuro-memory sync myagent
```

## Tips

- **Update MEMORY.md weekly** — Promote important items from daily logs
- **Review LOOPS.md daily** — Close stale loops, escalate blocked ones
- **Keep INBOX.md empty** — Process into proper files regularly
- **Use templates** — Copy from TEMPLATES/ for consistency
