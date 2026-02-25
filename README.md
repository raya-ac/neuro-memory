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

                        How NeuroMemory maps to it:

   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │   Atkinson-Shiffrin              NeuroMemory                        │
   │   ─────────────────              ───────────                        │
   │                                                                     │
   │   Sensory Memory      ───▶     (not implemented)                   │
   │   (raw input)                     agents handle this themselves    │
   │                                                                     │
   │   Short-Term Memory   ───▶     L1 Working Memory (Redis)           │
   │   (active thought)               hot cache, 5min TTL               │
   │                                                                     │
   │   Long-Term Memory    ───▶     L2-L4 Storage Layers                │
   │   ─────────────────                                              │
   │   ├─ Episodic         ───▶     L2 Episodic (SQLite)                │
   │   │  (what happened)             conversations, events, logs       │
   │   │                                                              │
   │   ├─ Semantic         ───▶     L3 Semantic (Neo4j)                 │
   │   │  (what's true)               knowledge graph, relationships   │
   │   │                                                              │
   │   └─ Procedural       ───▶     L4 Procedural (SQLite)             │
   │      (how to do)                 patterns, skills, procedures     │
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘
```

The original model had three stages: sensory, short-term, long-term. Later research split long-term memory into episodic, semantic, and procedural. That's where the four layers come from.

Why does this matter? Because vector databases treat all memory the same. But "I had coffee with Sarah yesterday" and "Sarah is a software engineer" and "I know how to brew coffee" are fundamentally different kinds of information. They should be stored differently, accessed differently, and they decay at different rates.

The Atkinson-Shiffrin model got some things wrong (memory isn't quite this linear), but the core insight holds: different types of memory serve different functions. This system tries to respect that.

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

Clone it:

```bash
git clone https://github.com/raya-ac/neuro-memory.git
cd neuro-memory
pip install -e .
```

Install Redis (Ubuntu/Debian):

```bash
apt install redis-server
systemctl enable redis-server
systemctl start redis-server
```

Install Neo4j:

```bash
wget -O - https://debian.neo4j.com/neodebgen.key | apt-key add -
echo 'deb https://debian.neo4j.com stable 4.0' | tee /etc/apt/sources.list.d/neo4j.list
apt update
apt install neo4j=1:4.0.12
systemctl enable neo4j
systemctl start neo4j
```

Disable Neo4j auth if you're running localhost-only:

```bash
sed -i 's/dbms.security.auth_enabled=true/dbms.security.auth_enabled=false/' /etc/neo4j/neo4j.conf
systemctl restart neo4j
```

Edit `config.json` to match your setup. The defaults work for a local install with auth disabled.

## Using it

Basic usage:

```python
import asyncio
from memory_integration import Memory

async def main():
    await Memory.initialize()
    
    # Remember something
    memory_id = await Memory.remember(
        "User prefers dark mode and concise responses",
        importance=0.8
    )
    
    # Find it later
    results = await Memory.recall("user preferences")
    for r in results:
        print(f"[{r['layer']}] {r['content']}")
    
    # Get context for a message
    context = await Memory.get_context_for_message("what does user like?")
    print(context)
    
    # Store a conversation
    await Memory.store_interaction(
        "What's your favorite color?",
        "I don't have preferences, but blue is popular!"
    )

asyncio.run(main())
```

If you've got markdown files you want indexed (agent notes, project docs, whatever):

```python
from integration import FileMemoryBridge

bridge = FileMemoryBridge("my-agent")
asyncio.run(bridge.initialize())
asyncio.run(bridge.ingest_workspace())

results = asyncio.run(bridge.search_across_layers("project status"))
```

## The maintenance scripts

There are three standalone scripts in `scripts/`:

```bash
# Check if everything's working
./scripts/memory_health.py

# Archive old stuff, promote important stuff (run nightly)
./scripts/memory_consolidate.py

# Sync markdown files from your workspace (run every few hours)
./scripts/memory_sync.py
```

Crontab:

```crontab
0 2 * * * /path/to/scripts/memory_consolidate.py >> /var/log/memory-consolidation.log 2>&1
0 * * * * /path/to/scripts/memory_health.py >> /var/log/memory-health.log 2>&1
0 */6 * * * /path/to/scripts/memory_sync.py >> /var/log/memory-sync.log 2>&1
```

## Each layer in detail

### L1 Working Memory (Redis)

This is the hot cache. Whatever you're actively working on goes here. It expires after 5 minutes by default because working memory shouldn't be permanent.

```python
await Memory.remember("current task", layer=MemoryLayer.WORKING)
```

Use it for: recent conversation, active context, stuff you'll need in the next few minutes.

### L2 Episodic Memory (SQLite)

Events, conversations, daily logs. This is the default layer. Sticks around for 90 days before getting archived.

```python
await Memory.remember("Met with team about project timeline")
await Memory.store_interaction(user_msg, assistant_msg)
```

Use it for: session logs, daily notes, anything time-based.

### L3 Semantic Memory (Neo4j)

The knowledge graph. Entities and relationships. If you're storing "Alice works with Bob on Project X", this is where it goes.

```python
await Memory.remember(
    "Alice works on the Phoenix project with Bob",
    entities=[
        {"name": "Alice", "type": "person"},
        {"name": "Phoenix", "type": "project"},
        {"name": "Bob", "type": "person"}
    ]
)

# Find related memories through the graph
related = await Memory.find_related(memory_id, depth=2)
```

Use it for: facts, concepts, who-knows-what relationships.

### L4 Procedural Memory (SQLite)

Patterns and skills. Not fully fleshed out yet, but tracks what works and what doesn't.

Use it for: learned patterns, reusable procedures, "how to" knowledge.

## How memories move between layers

```
Working (L1) → Episodic (L2) → Semantic (L3)
     ↓              ↓               ↓
   Evict        Archive       Consolidate
   (TTL)       (90 days)     (entities)
```

High-importance stuff bubbles up. Low-access stuff fades. Old episodic memories get archived (not deleted - you might want them later). The consolidation job runs nightly and handles all of this.

## Project structure

```
neuro-memory/
├── config.json           # Configuration
├── setup.py              # Package setup
├── core/
│   ├── base.py          # Base classes, types
│   ├── manager.py       # Layer orchestration
│   └── lifecycle.py     # Promotion/demotion logic
├── layers/
│   ├── working.py       # L1 Redis implementation
│   ├── episodic.py      # L2 SQLite implementation
│   ├── semantic.py      # L3 Neo4j implementation
│   └── procedural.py    # L4 SQLite implementation
├── scripts/
│   ├── memory_health.py       # Health check
│   ├── memory_consolidate.py  # Nightly maintenance
│   └── memory_sync.py         # File sync
├── integration.py        # File-to-memory bridge
└── bridge.py            # Legacy sync bridge
```

## API

```python
class MemoryIntegration:
    async def initialize() -> bool
    async def remember(content, importance=0.5, ...) -> str
    async def recall(query, limit=10) -> List[Dict]
    async def recall_recent(hours=24) -> List[Dict]
    async def find_related(memory_id, depth=2) -> List[Dict]
    async def get_context_for_message(message) -> str
    async def store_interaction(user_msg, assistant_msg, importance=0.6)
    async def get_stats() -> Dict
    async def shutdown()
```

## Performance

| Layer | Latency | Target |
|-------|---------|--------|
| L1 Working | ~1ms | <5ms |
| L2 Episodic | ~5ms | <10ms |
| L3 Semantic | ~15ms | <20ms |
| L4 Procedural | ~3ms | <10ms |

Hit rates settle around 90%+ after the system warms up.

## When things break

Neo4j won't connect:

```bash
systemctl status neo4j
tail -f /var/log/neo4j/neo4j.log
python3 -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://localhost:7687'); print('OK')"
```

Redis won't connect:

```bash
redis-cli ping
# Should say PONG
```

SQLite databases are created automatically in the same directory as the code: `episodic.db` and `procedural.db`.

## License

MIT. Do whatever.

## Why this exists

I kept running into the same problem: AI agents that couldn't remember anything between sessions. Every conversation started from scratch. No learning, no continuity, no way to build up actual knowledge about users or projects.

There are plenty of vector database solutions out there, but they're all basically the same thing: semantic search over embeddings. Useful, but not how memory actually works. Humans don't just have one kind of memory. We've got working memory for what's immediate, episodic for what happened, semantic for what's true, and procedural for what we know how to do.

This system tries to replicate that structure. It's not perfect, but it's been working well enough that I figured others might find it useful.

Based loosely on the Atkinson-Shiffrin model from cognitive psychology, if you care about that sort of thing.
