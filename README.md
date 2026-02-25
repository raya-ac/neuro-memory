# NeuroMemory

A 4-layer memory system for AI agents. Built because I got tired of agents forgetting everything between sessions.

The idea is simple: model memory after how humans actually work. We've got working memory (what you're thinking about right now), episodic memory (what happened), semantic memory (facts and relationships), and procedural memory (how to do things). This system does the same thing, but for AI.

All four layers run under 20ms. Most operations are single-digit milliseconds.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                    NeuroMemory System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  L1 Working Memory (Redis)     ~1ms                            │
│  ├── Hot cache for current session                              │
│  ├── LRU eviction, TTL-based                                    │
│  └── Max 8000 tokens, 5min TTL                                  │
│                                                                  │
│  L2 Episodic Memory (SQLite)   ~5ms                            │
│  ├── Temporal sequence storage                                  │
│  ├── 90-day retention, auto-archival                            │
│  └── Full-text search enabled                                   │
│                                                                  │
│  L3 Semantic Memory (Neo4j)    ~15ms                           │
│  ├── Knowledge graph with entities                              │
│  ├── Relationship tracking                                      │
│  └── Multi-hop graph traversal                                  │
│                                                                  │
│  L4 Procedural Memory (SQLite) ~3ms                            │
│  ├── Pattern/skill storage                                      │
│  ├── Success rate tracking                                      │
│  └── Template-based execution                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Memories flow upward as they become more important. Hot stuff sits in Redis for instant access. Conversations go to SQLite. Facts and relationships end up in Neo4j's graph. Patterns and skills live in their own SQLite DB.

The system handles promotion and demotion automatically. If you keep accessing something, it moves up. If something sits untouched, it eventually gets archived.

## The psychology behind it

This is based on the Atkinson-Shiffrin model from 1968. If you took Psych 101, you've probably seen this:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Atkinson-Shiffrin Memory Model (1968)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐         │
│   │   Sensory   │        │   Short-    │        │    Long-    │         │
│   │   Memory    │───────▶│   Term      │───────▶│    Term     │         │
│   │             │        │   Memory    │        │    Memory   │         │
│   └─────────────┘        └─────────────┘        └─────────────┘         │
│         │                      │                      │                  │
│    < 1 second            15-30 seconds           Lifetime                │
│    Raw perception        Active processing        Permanent store        │
│    (vision, sound)       (what you're thinking)   (knowledge, skills)    │
│                                                                           │
│                          ┌─────────────────────────────────────┐         │
│                          │          Long-Term Memory           │         │
│                          │  ┌───────────┬───────────┬───────┐ │         │
│                          │  │ Episodic  │ Semantic  │Proced-│ │         │
│                          │  │           │           │  ural │ │         │
│                          │  │ Events    │ Facts     │Skills │ │         │
│                          │  │ Experiences│ Concepts │Habits │ │         │
│                          │  └───────────┴───────────┴───────┘ │         │
│                          └─────────────────────────────────────┘         │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

Why does this matter? Because vector databases treat all memory the same. But "I had coffee with Sarah yesterday" and "Sarah is a software engineer" and "I know how to brew coffee" are fundamentally different kinds of information. They should be stored differently, accessed differently, and they decay at different rates.

---

## What you need

- Python 3.10+
- Redis
- Neo4j 4.x
- SQLite (comes with Python)

```bash
pip install neo4j redis asyncio
```

## Setup

```bash
git clone https://github.com/raya-ac/neuro-memory.git
cd neuro-memory
pip install -e .
```

Install Redis and Neo4j, then:

```bash
# Install the CLI
ln -s $(pwd)/scripts/neuro-memory /usr/local/bin/neuro-memory

# Check everything's working
neuro-memory health
```

## The CLI

Unified command-line interface for everything:

```bash
# Get session context at startup (for agents)
neuro-memory session ava

# Search memories
neuro-memory recall eva "discord bot"

# Recent 24h memories
neuro-memory recent ava

# Memory statistics
neuro-memory stats eva

# Health check all 4 layers
neuro-memory health

# Sync workspace files to memory
neuro-memory sync ava

# Run consolidation (promote, archive, cleanup)
neuro-memory groom
```

## Agent Workspace Template

Includes a complete workspace template for setting up new agents:

```bash
cp -r examples/workspace-template ~/.openclaw/workspace-myagent
```

The template includes:

```
workspace-template/
├── AGENTS.md          # Boot sequence & rules
├── SOUL.md            # Core personality
├── IDENTITY.md        # Name, emoji, avatar
├── USER.md            # Human context
├── TOOLS.md           # Environment notes
├── HEARTBEAT.md       # Periodic tasks
│
├── mind/              # Persistent cognition
│   ├── MEMORY.md      # Long-term memory
│   ├── PROFILE.md     # Human profile
│   ├── PROJECTS.md    # Active projects
│   ├── GOALS.md       # Goal tracking
│   ├── DECISIONS.md   # Decision log
│   ├── ERRORS.md      # Anti-repeat patterns
│   ├── LOOPS.md       # Open loops
│   ├── INBOX.md       # Quick capture
│   ├── SHARED.md      # Cross-agent coord
│   └── TEMPLATES/     # Reusable templates
│
└── memory/            # Daily logs
```

See `examples/workspace-template/README.md` for details.

## Task Memory

Track work progress across sessions:

```bash
# Start a task
python3 scripts/memory_task.py ava start "fix-gateway" "Fixing gateway crash"

# Update progress
python3 scripts/memory_task.py ava update "fix-gateway" "50%" "Found root cause"

# Complete
python3 scripts/memory_task.py ava complete "fix-gateway" "Fixed by updating config"

# Pause (user wants to stop)
python3 scripts/memory_task.py ava abandon "fix-gateway" "User said stop"

# Failed
python3 scripts/memory_task.py ava fail "fix-gateway" "Couldn't reproduce"
```

Tasks are stored in episodic memory, so agents can resume work after session restarts.

## Crontab

```crontab
# Nightly consolidation
0 2 * * * neuro-memory groom >> /var/log/memory-groom.log 2>&1

# Hourly health check
0 * * * * neuro-memory health >> /var/log/memory-health.log 2>&1

# Sync workspaces every 6 hours
0 */6 * * * neuro-memory sync ava >> /var/log/memory-sync-ava.log 2>&1
0 3,9,15,21 * * * neuro-memory sync eva >> /var/log/memory-sync-eva.log 2>&1
```

## Using it in Python

```python
import asyncio
from memory_integration import Memory

async def main():
    await Memory.initialize()
    
    # Remember something
    await Memory.remember(
        "User prefers dark mode and concise responses",
        importance=0.8
    )
    
    # Find it later
    results = await Memory.recall("user preferences")
    for r in results:
        print(f"[{r.layer}] {r.content}")
    
    # Get context for a message
    context = await Memory.get_context_for_message("what does user like?")
    
    # Store a conversation
    await Memory.store_interaction(
        "What's your favorite color?",
        "I don't have preferences, but blue is popular!"
    )

asyncio.run(main())
```

## Project structure

```
neuro-memory/
├── core/
│   ├── base.py          # Base classes, types
│   ├── manager.py       # Layer orchestration
│   └── consolidator.py  # Smart consolidation
├── layers/
│   ├── working.py       # L1 Redis
│   ├── episodic.py      # L2 SQLite
│   ├── semantic.py      # L3 Neo4j
│   └── procedural.py    # L4 SQLite
├── scripts/
│   ├── neuro-memory     # Unified CLI
│   ├── memory_task.py   # Task tracking
│   ├── memory_health.py
│   ├── memory_sync.py
│   └── memory_consolidate.py
├── examples/
│   └── workspace-template/  # Agent workspace template
├── integration.py       # File-to-memory bridge
└── config.json          # Configuration
```

## Performance

| Layer | Latency | Target |
|-------|---------|--------|
| L1 Working | ~1ms | <5ms |
| L2 Episodic | ~5ms | <10ms |
| L3 Semantic | ~15ms | <20ms |
| L4 Procedural | ~3ms | <10ms |

## License

MIT. Do whatever.

---

I kept running into the same problem: AI agents that couldn't remember anything between sessions. Every conversation started from scratch. No learning, no continuity, no way to build up actual knowledge.

There are plenty of vector database solutions out there, but they're all basically the same thing: semantic search over embeddings. Useful, but not how memory actually works. Humans don't just have one kind of memory.

This system tries to replicate that structure. It's been working well enough that I figured others might find it useful.
