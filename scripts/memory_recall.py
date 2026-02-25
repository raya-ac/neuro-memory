#!/usr/bin/env python3
"""
Memory Recall Script - Quick CLI for recalling memories

Usage:
    python3 memory_recall.py <agent> session_start   # Get session context
    python3 memory_recall.py <agent> search <query>  # Search memories
    python3 memory_recall.py <agent> recent          # Recent 24h memories
    python3 memory_recall.py <agent> stats           # Memory stats
"""

import asyncio
import sys
import os
import json

# Add paths
sys.path.insert(0, '/root/.openclaw/memory-system')

# Agent workspace mapping
AGENT_WORKSPACES = {
    'ava': '/root/.openclaw/workspace-ava',
    'eva': '/root/.openclaw/workspace-eva',
}

from core.manager import NeuroMemoryManager
from core.base import MemoryLayer


async def recall_session_context(agent: str):
    """Get relevant context for starting a new session"""
    manager = NeuroMemoryManager()
    await manager.connect()
    
    print(f"🧠 Recalling context for {agent.upper()}...\n")
    
    # Search for key context areas
    context_queries = [
        "project status",
        "active work", 
        "recent decisions",
        "important context",
        "user preferences"
    ]
    
    all_results = []
    for query in context_queries:
        results = await manager.recall(query, limit=3)
        for r in results:
            if r.id not in [x.id for x in all_results]:
                all_results.append(r)
    
    # Get recent memories
    recent = await manager.recall_recent(hours=48, limit=10)
    
    # Get stats
    stats = await manager.get_stats()
    
    print("=" * 60)
    print("SESSION CONTEXT RECALL")
    print("=" * 60)
    
    print(f"\n📊 Memory Stats:")
    print(f"   Working: {stats['working'].get('items_in_cache', 0)} items")
    print(f"   Episodic: {stats['episodic'].get('total_memories', 0)} memories")
    print(f"   Semantic: {stats['semantic'].get('memories', 0)} memories, {stats['semantic'].get('entities', 0)} entities")
    print(f"   Procedural: {stats['procedural'].get('total_patterns', 0)} patterns")
    
    if all_results:
        print(f"\n🎯 Relevant Context ({len(all_results)} items):")
        for r in all_results[:10]:
            layer_icon = {'working': '⚡', 'episodic': '📅', 'semantic': '🧠', 'procedural': '🔧'}.get(r.layer.value, '•')
            content = r.content[:150] + '...' if len(r.content) > 150 else r.content
            source = r.metadata.get('source_file', '') if r.metadata else ''
            print(f"   {layer_icon} [{r.layer.value:10}] {content}")
            if source:
                print(f"      📁 {source}")
    
    if recent:
        print(f"\n📅 Recent Memories (48h):")
        for r in recent[:5]:
            content = r.content[:100] + '...' if len(r.content) > 100 else r.content
            print(f"   • {content}")
    
    print("\n" + "=" * 60)
    
    await manager.disconnect()


async def search_memories(agent: str, query: str):
    """Search memories for a query"""
    manager = NeuroMemoryManager()
    await manager.connect()
    
    print(f"🔍 Searching memories for: '{query}'\n")
    
    results = await manager.recall(query, limit=15)
    
    if not results:
        print("No results found.")
    else:
        print(f"Found {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            layer_icon = {'working': '⚡', 'episodic': '📅', 'semantic': '🧠', 'procedural': '🔧'}.get(r.layer.value, '•')
            print(f"{i}. {layer_icon} [{r.layer.value}] (importance: {r.importance:.2f})")
            print(f"   {r.content[:200]}{'...' if len(r.content) > 200 else ''}")
            if r.metadata and r.metadata.get('source_file'):
                print(f"   📁 {r.metadata['source_file']}")
            print()
    
    await manager.disconnect()


async def get_recent(agent: str):
    """Get recent memories"""
    manager = NeuroMemoryManager()
    await manager.connect()
    
    print(f"📅 Recent memories for {agent.upper()}\n")
    
    recent = await manager.recall_recent(hours=24, limit=20)
    
    if not recent:
        print("No recent memories.")
    else:
        for r in recent:
            content = r.content[:150] + '...' if len(r.content) > 150 else r.content
            print(f"• {content}")
    
    await manager.disconnect()


async def get_stats(agent: str):
    """Get memory statistics"""
    manager = NeuroMemoryManager()
    await manager.connect()
    
    stats = await manager.get_stats()
    
    print(json.dumps(stats, indent=2, default=str))
    
    await manager.disconnect()


async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nExamples:")
        print("  python3 memory_recall.py ava session_start")
        print("  python3 memory_recall.py ava search 'discord bot'")
        print("  python3 memory_recall.py ava recent")
        print("  python3 memory_recall.py ava stats")
        sys.exit(1)
    
    agent = sys.argv[1]
    command = sys.argv[2]
    
    if command == "session_start":
        await recall_session_context(agent)
    elif command == "search":
        if len(sys.argv) < 4:
            print("Usage: memory_recall.py <agent> search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[3:])
        await search_memories(agent, query)
    elif command == "recent":
        await get_recent(agent)
    elif command == "stats":
        await get_stats(agent)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
