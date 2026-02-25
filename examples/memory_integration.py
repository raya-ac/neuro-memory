#!/usr/bin/env python3
"""
OpenClaw Integration for NeuroMemory System

This module integrates the 4-layer NeuroMemory system with OpenClaw sessions.
Import and use in your OpenClaw agent to enable cognitive memory.

Usage:
    from memory_integration import Memory
    
    # During session boot
    await Memory.initialize()
    
    # Store a memory
    await Memory.remember("User prefers dark mode", importance=0.8)
    
    # Recall relevant memories
    results = await Memory.recall("user preferences")
    
    # Get context for current session
    context = await Memory.get_session_context()
"""

import asyncio
import json
import os
import sys
from typing import List, Optional, Dict, Any
from datetime import datetime

# Add memory-system to path
MEMORY_SYSTEM_PATH = "/root/.openclaw/memory-system"
if MEMORY_SYSTEM_PATH not in sys.path:
    sys.path.insert(0, MEMORY_SYSTEM_PATH)

from core.manager import NeuroMemoryManager
from core.base import MemoryLayer

# Import new features
try:
    from layers.entity_extractor import EntityExtractor
    ENTITY_EXTRACTION = True
except ImportError:
    ENTITY_EXTRACTION = False

try:
    from layers.embeddings import generate_embedding
    EMBEDDINGS = True
except ImportError:
    EMBEDDINGS = False

class MemoryIntegration:
    """
    Singleton integration class for OpenClaw sessions.
    Provides easy access to all 4 memory layers.
    """
    
    _instance = None
    _manager: Optional[NeuroMemoryManager] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> bool:
        """Initialize the memory system - call once per session"""
        if self._initialized:
            return True
            
        try:
            self._manager = NeuroMemoryManager()
            await self._manager.connect()
            self._initialized = True
            
            # Store session start in episodic memory
            await self.remember(
                content=f"Session started at {datetime.utcnow().isoformat()}",
                layer=MemoryLayer.EPISODIC,
                importance=0.5,
                metadata={"type": "session_start"}
            )
            
            return True
        except Exception as e:
            print(f"Memory initialization failed: {e}", file=sys.stderr)
            return False
    
    async def shutdown(self):
        """Clean shutdown"""
        if self._manager:
            await self.remember(
                content=f"Session ended at {datetime.utcnow().isoformat()}",
                layer=MemoryLayer.EPISODIC,
                importance=0.4,
                metadata={"type": "session_end"}
            )
            await self._manager.disconnect()
            self._initialized = False
    
    async def remember(self, content: str, 
                      layer: MemoryLayer = MemoryLayer.EPISODIC,
                      importance: float = 0.5,
                      metadata: Dict = None,
                      entities: List[Dict] = None,
                      auto_extract: bool = True) -> Optional[str]:
        """
        Store a memory in the specified layer.
        
        Args:
            content: The memory content
            layer: Which layer to store in (default: EPISODIC)
            importance: 0-1 importance score
            metadata: Optional dict of additional metadata
            entities: Optional list of entities to extract (for SEMANTIC)
            auto_extract: Auto-extract entities and generate embeddings (default: True)
        
        Returns:
            Memory ID if successful, None otherwise
        """
        if not self._initialized or not self._manager:
            return None
        
        # Auto-extract entities if not provided
        if auto_extract and ENTITY_EXTRACTION and not entities:
            extractor = EntityExtractor()
            extracted_entities, relationships = extractor.extract_entities(content), []
            if extracted_entities:
                entities = [
                    {'name': e.name, 'type': e.type, 'canonical': e.canonical}
                    for e in extracted_entities[:10]  # Limit to top 10
                ]
                metadata = metadata or {}
                metadata['auto_entities'] = True
        
        # Generate embedding (stored in metadata for now, manager doesn't support embedding param yet)
        embedding = None
        embedding_b64 = None
        if auto_extract and EMBEDDINGS:
            embedding = generate_embedding(content)
            if embedding is not None:
                from layers.embeddings import embedding_to_base64
                embedding_b64 = embedding_to_base64(embedding)
                metadata = metadata or {}
                metadata['embedding_b64'] = embedding_b64
            
        try:
            memory_id = await self._manager.remember(
                content=content,
                layer=layer,
                importance=importance,
                metadata=metadata or {},
                entities=entities
            )
            return memory_id
        except Exception as e:
            print(f"Failed to store memory: {e}", file=sys.stderr)
            return None
    
    async def recall(self, query: str, 
                    layers: List[MemoryLayer] = None,
                    limit: int = 10,
                    use_embeddings: bool = True) -> List[Dict]:
        """
        Search for memories across all layers.
        
        Args:
            query: Search query
            layers: Specific layers to search (default: all)
            limit: Max results per layer
            use_embeddings: Use semantic similarity (default: True)
        
        Returns:
            List of memory results with layer info
        """
        if not self._initialized or not self._manager:
            return []
        
        try:
            # Generate query embedding for hybrid search (stored in metadata for matching)
            query_embedding = None
            if use_embeddings and EMBEDDINGS:
                query_embedding = generate_embedding(query)
            
            memories = await self._manager.recall(
                query=query,
                layers=layers,
                limit=limit
            )
            
            # If we have embeddings, we could re-rank results here
            # For now, just return as-is
            
            # Convert to dicts for easy use
            results = []
            for m in memories:
                results.append({
                    'id': m.id,
                    'content': m.content,
                    'layer': m.layer.value,
                    'importance': m.importance,
                    'created_at': m.created_at,
                    'access_count': m.access_count
                })
            return results
        except Exception as e:
            print(f"Failed to recall memories: {e}", file=sys.stderr)
            return []
    
    async def recall_recent(self, hours: int = 24) -> List[Dict]:
        """Get recent memories from episodic layer"""
        if not self._initialized or not self._manager:
            return []
            
        try:
            memories = await self._manager.recall_recent(hours=hours)
            return [
                {
                    'id': m.id,
                    'content': m.content,
                    'importance': m.importance,
                    'created_at': m.created_at
                }
                for m in memories
            ]
        except Exception as e:
            print(f"Failed to get recent memories: {e}", file=sys.stderr)
            return []
    
    async def find_related(self, memory_id: str, depth: int = 2) -> List[Dict]:
        """Find semantically related memories (graph traversal)"""
        if not self._initialized or not self._manager:
            return []
            
        try:
            related = await self._manager.find_related(memory_id, depth=depth)
            return [
                {
                    'id': r['memory'].id,
                    'content': r['memory'].content,
                    'distance': r['distance'],
                    'importance': r['memory'].importance
                }
                for r in related
            ]
        except Exception as e:
            print(f"Failed to find related memories: {e}", file=sys.stderr)
            return []
    
    async def get_context_for_message(self, message: str) -> str:
        """
        Get relevant context for a user message.
        Returns formatted string for inclusion in system prompt.
        """
        if not self._initialized:
            return ""
            
        # Search for relevant memories
        results = await self.recall(message, limit=5)
        
        if not results:
            return ""
        
        # Format for prompt
        context_lines = ["\n### Relevant Context from Memory"]
        for r in results[:5]:
            layer_icon = {
                'working': '⚡',
                'episodic': '📅', 
                'semantic': '🧠',
                'procedural': '🔧'
            }.get(r['layer'], '•')
            
            # Truncate long content
            content = r['content'][:200] + '...' if len(r['content']) > 200 else r['content']
            context_lines.append(f"{layer_icon} [{r['layer']}] {content}")
        
        return '\n'.join(context_lines)
    
    async def get_session_context(self) -> Dict[str, Any]:
        """Get full context for current session"""
        if not self._initialized or not self._manager:
            return {}
            
        try:
            stats = await self._manager.get_stats()
            recent = await self.recall_recent(hours=24)
            
            return {
                'stats': stats,
                'recent_memories': recent,
                'total_24h': len(recent)
            }
        except Exception as e:
            print(f"Failed to get session context: {e}", file=sys.stderr)
            return {}
    
    async def store_interaction(self, user_msg: str, assistant_msg: str, 
                               importance: float = 0.6):
        """Store a conversation turn in episodic memory"""
        content = f"User: {user_msg}\nAssistant: {assistant_msg}"
        await self.remember(
            content=content,
            layer=MemoryLayer.EPISODIC,
            importance=importance,
            metadata={"type": "conversation", "has_response": True}
        )
    
    async def get_stats(self) -> Dict:
        """Get memory system statistics"""
        if not self._initialized or not self._manager:
            return {"status": "not_initialized"}
        return await self._manager.get_stats()


# Global singleton instance
Memory = MemoryIntegration()


# Convenience functions for direct use
async def init_memory() -> bool:
    """Initialize memory system"""
    return await Memory.initialize()

async def remember(content: str, importance: float = 0.5, **kwargs) -> Optional[str]:
    """Store a memory"""
    return await Memory.remember(content=content, importance=importance, **kwargs)

async def recall(query: str, **kwargs) -> List[Dict]:
    """Search memories"""
    return await Memory.recall(query=query, **kwargs)

async def get_context(message: str) -> str:
    """Get context for a message"""
    return await Memory.get_context_for_message(message)


if __name__ == "__main__":
    # Test the integration
    async def test():
        print("Testing NeuroMemory integration...")
        
        # Initialize
        success = await Memory.initialize()
        print(f"Initialization: {'✓' if success else '✗'}")
        
        if success:
            # Store test memory
            mid = await Memory.remember(
                "Test memory from integration module",
                importance=0.7
            )
            print(f"Stored memory: {mid}")
            
            # Recall
            results = await Memory.recall("test memory")
            print(f"Found {len(results)} results")
            
            # Get stats
            stats = await Memory.get_stats()
            print(f"Stats: {json.dumps(stats, indent=2, default=str)}")
            
            # Shutdown
            await Memory.shutdown()
            print("Shutdown complete")
    
    asyncio.run(test())
