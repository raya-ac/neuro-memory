"""
NeuroMemory System - 4-Layer Cognitive Memory Architecture

A high-performance memory system for AI agents with:
- L1: Working Memory (Redis) - Hot cache
- L2: Episodic Memory (SQLite) - Recent events
- L3: Semantic Memory (Neo4j) - Knowledge graph
- L4: Procedural Memory (SQLite) - Patterns

Usage:
    from memory_system import NeuroMemoryManager
    
    manager = NeuroMemoryManager()
    await manager.connect()
    
    # Store memory
    memory_id = await manager.remember("Important context", layer=MemoryLayer.EPISODIC)
    
    # Retrieve
    results = await manager.recall("query")
    
    await manager.disconnect()
"""

from .core.base import MemoryEntry, MemoryLayer, MemoryLifecycle
from .core.manager import NeuroMemoryManager
from .predictive.engine import PredictiveEngine

__version__ = "1.0.0"
__all__ = [
    "MemoryEntry",
    "MemoryLayer", 
    "MemoryLifecycle",
    "NeuroMemoryManager",
    "PredictiveEngine"
]
