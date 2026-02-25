#!/usr/bin/env python3
"""
Memory System Integration - Bridges file-based memory with 4-layer cognitive architecture
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import asyncio

# Add memory-system to path
sys.path.insert(0, '/root/.openclaw/memory-system')

from core.base import MemoryEntry, MemoryLayer
from core.manager import NeuroMemoryManager


class FileMemoryBridge:
    """
    Bridges existing file-based memory (AGENTS.md, mind/, memory/)
    with the 4-layer cognitive memory system
    """
    
    def __init__(self, agent_name: str = "ava"):
        self.agent_name = agent_name
        self.workspace = f"/root/.openclaw/workspace-{agent_name}"
        self.mind_dir = f"{self.workspace}/mind"
        self.memory_dir = f"{self.workspace}/memory"
        self.manager: Optional[NeuroMemoryManager] = None
    
    async def initialize(self):
        """Initialize the 4-layer memory system"""
        self.manager = NeuroMemoryManager(
            redis_url="redis://localhost:6379",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user=None,
            neo4j_pass=None
        )
        await self.manager.connect()
        print(f"✓ {self.agent_name.upper()} memory system initialized")
    
    def file_to_memory_entry(self, file_path: str, content: str) -> MemoryEntry:
        """Convert a file to a memory entry"""
        # Generate ID from path + hash
        file_hash = hashlib.md5(f"{file_path}:{content[:100]}".encode()).hexdigest()[:12]
        memory_id = f"file:{file_hash}"
        
        # Determine layer based on file type
        if 'memory/' in file_path and datetime.now().strftime('%Y-%m-%d') in file_path:
            layer = MemoryLayer.WORKING
        elif 'mind/DECISIONS.md' in file_path or 'mind/ERRORS.md' in file_path:
            layer = MemoryLayer.SEMANTIC
        elif 'mind/LOOPS.md' in file_path:
            layer = MemoryLayer.PROCEDURAL
        else:
            layer = MemoryLayer.EPISODIC
        
        # Calculate importance based on file type
        importance = 0.5
        if 'SOUL.md' in file_path or 'AGENTS.md' in file_path:
            importance = 1.0
        elif 'DECISIONS.md' in file_path:
            importance = 0.9
        elif 'ERRORS.md' in file_path:
            importance = 0.8
        
        # Get file modification time
        mtime = os.path.getmtime(file_path)
        
        return MemoryEntry(
            id=memory_id,
            content=content[:8000],  # Limit size
            layer=layer,
            importance=importance,
            created_at=mtime,
            last_accessed=mtime,
            metadata={
                'source_file': file_path,
                'agent': self.agent_name,
                'file_type': Path(file_path).suffix or '.md'
            }
        )
    
    async def ingest_workspace(self):
        """Ingest all files from workspace into memory layers"""
        print(f"\n📥 Ingesting {self.agent_name}'s workspace...")
        
        files_processed = 0
        
        # Ingest mind/ files
        if os.path.exists(self.mind_dir):
            for root, _, files in os.walk(self.mind_dir):
                for filename in files:
                    if filename.endswith('.md'):
                        filepath = os.path.join(root, filename)
                        try:
                            with open(filepath, 'r') as f:
                                content = f.read()
                            
                            entry = self.file_to_memory_entry(filepath, content)
                            await self.manager.remember(entry.content, {
                                'layer': entry.layer.value,
                                'importance': entry.importance,
                                'metadata': entry.metadata
                            })
                            files_processed += 1
                        except Exception as e:
                            print(f"  ⚠ Error processing {filepath}: {e}")
        
        # Ingest memory/ files (daily logs)
        if os.path.exists(self.memory_dir):
            for filename in os.listdir(self.memory_dir):
                if filename.endswith('.md'):
                    filepath = os.path.join(self.memory_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                        
                        entry = self.file_to_memory_entry(filepath, content)
                        await self.manager.remember(entry.content, {
                            'layer': 'episodic',
                            'importance': 0.6,
                            'metadata': entry.metadata
                        })
                        files_processed += 1
                    except Exception as e:
                        print(f"  ⚠ Error processing {filepath}: {e}")
        
        print(f"✓ Processed {files_processed} files")
        return files_processed
    
    async def search_across_layers(self, query: str, limit: int = 10) -> List[Dict]:
        """Search across all 4 memory layers"""
        results = await self.manager.recall(query, {'limit': limit})
        return [r.to_dict() for r in results]
    
    async def get_context_for_query(self, query: str) -> str:
        """Get relevant context from memory for a query"""
        results = await self.search_across_layers(query, limit=5)
        
        context_parts = []
        for r in results:
            source = r.get('metadata', {}).get('source_file', 'unknown')
            content = r['content'][:500]  # First 500 chars
            context_parts.append(f"[{r['layer']}] {source}:\n{content}\n")
        
        return "\n".join(context_parts)
    
    async def promote_important_memories(self):
        """Auto-promote high-importance memories through layers"""
        print(f"\n🔄 Checking for memory promotions...")
        stats = await self.manager.optimize_layers()
        print(f"  Promoted: {stats['promoted']}, Demoted: {stats['demoted']}")
        return stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return self.manager.get_all_stats()
    
    async def close(self):
        """Shutdown memory system"""
        if self.manager:
            await self.manager.disconnect()


async def main():
    """Demo: Initialize and test memory system for both agents"""
    print("=" * 60)
    print("OPENCLAW 4-LAYER COGNITIVE MEMORY SYSTEM")
    print("=" * 60)
    
    # Initialize Ava
    ava_bridge = FileMemoryBridge("ava")
    await ava_bridge.initialize()
    await ava_bridge.ingest_workspace()
    
    # Initialize Eva
    eva_bridge = FileMemoryBridge("eva")
    await eva_bridge.initialize()
    await eva_bridge.ingest_workspace()
    
    # Demo search
    print("\n🔍 Demo Search: 'memory system'")
    results = await ava_bridge.search_across_layers("memory system", limit=3)
    for r in results:
        print(f"  [{r['layer']}] {r['id']} (importance: {r['importance']:.2f})")
    
    # Show stats
    print("\n📊 Ava Memory Stats:")
    stats = ava_bridge.get_stats()
    for layer, data in stats.items():
        print(f"  {layer}: {data}")
    
    # Cleanup
    await ava_bridge.close()
    await eva_bridge.close()
    
    print("\n✓ Memory system demo complete")


if __name__ == "__main__":
    asyncio.run(main())
