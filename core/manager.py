#!/usr/bin/env python3
"""
NeuroMemoryManager - Main orchestrator for 4-layer cognitive memory
Coordinates between working, episodic, semantic, and procedural layers
"""

import asyncio
import hashlib
import json
import time
import uuid
from typing import List, Optional, Dict, Any, Callable
from dataclasses import asdict

from .base import MemoryEntry, MemoryLayer, MemoryLifecycle
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import MemoryEntry, MemoryLayer, MemoryLifecycle
from layers.working import WorkingMemoryLayer
from layers.episodic import EpisodicMemoryLayer
from layers.semantic import SemanticMemoryLayer
from layers.procedural import ProceduralMemoryLayer

import logging
logger = logging.getLogger("neuro-memory.manager")


class NeuroMemoryManager:
    """
    Unified interface for the 4-layer cognitive memory system
    Handles promotion/demotion, cross-layer queries, and lifecycle management
    """
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379",
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_pass: str = None):
        
        # Load password from config if not provided
        if neo4j_pass is None:
            neo4j_pass = self._load_neo4j_password()
        
        # Initialize layers
        self.working = WorkingMemoryLayer(redis_url)
        self.episodic = EpisodicMemoryLayer()
        self.semantic = SemanticMemoryLayer(neo4j_uri, neo4j_user, neo4j_pass)
        self.procedural = ProceduralMemoryLayer()
        
        self.lifecycle = MemoryLifecycle()
        self._connected = False
        
        # Callbacks for layer transitions
        self._promotion_callbacks: List[Callable] = []
        self._demotion_callbacks: List[Callable] = []
    
    def _load_neo4j_password(self) -> str:
        """Load Neo4j password from config.json"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('memory', {}).get('hierarchy', {}).get('semantic', {}).get('neo4j_pass', 'password')
        except Exception as e:
            logger.warning(f"Could not load config, using default password: {e}")
            return "password"
    
    async def connect(self):
        """Initialize all layers - continues even if some fail"""
        errors = []
        
        try:
            await self.working.connect()
            logger.info("✓ Working memory (Redis) connected")
        except Exception as e:
            errors.append(f"Working: {e}")
            logger.warning(f"Working memory unavailable: {e}")
        
        try:
            self.episodic.connect()
            logger.info("✓ Episodic memory (SQLite) connected")
        except Exception as e:
            errors.append(f"Episodic: {e}")
            logger.warning(f"Episodic memory unavailable: {e}")
        
        try:
            await self.semantic.connect()
            logger.info("✓ Semantic memory (Neo4j) connected")
        except Exception as e:
            errors.append(f"Semantic: {e}")
            logger.warning(f"Semantic memory unavailable: {e}")
        
        try:
            self.procedural.connect()
            logger.info("✓ Procedural memory (SQLite) connected")
        except Exception as e:
            errors.append(f"Procedural: {e}")
            logger.warning(f"Procedural memory unavailable: {e}")
        
        self._connected = True
        if errors:
            logger.warning(f"Connected with {len(errors)} layer(s) unavailable")
        else:
            logger.info("All 4 memory layers connected")
    
    async def disconnect(self):
        """Close all layers - ignore errors"""
        try:
            await self.working.disconnect()
        except:
            pass
        try:
            self.episodic.disconnect()
        except:
            pass
        try:
            await self.semantic.disconnect()
        except:
            pass
        try:
            self.procedural.disconnect()
        except:
            pass
        self._connected = False
    
    async def remember(self, content: str, 
                      layer: MemoryLayer = MemoryLayer.EPISODIC,
                      importance: float = 0.5,
                      metadata: Optional[Dict] = None,
                      entities: Optional[List[Dict]] = None) -> str:
        """
        Store a memory in the appropriate layer
        
        Args:
            content: The memory content
            layer: Which layer to store in (default: EPISODIC)
            importance: Initial importance score (0-1)
            metadata: Additional metadata
            entities: Extracted entities for semantic layer
        
        Returns:
            memory_id: Unique identifier for the memory
        """
        memory_id = str(uuid.uuid4())
        
        memory = MemoryEntry(
            id=memory_id,
            content=content,
            layer=layer,
            importance=importance,
            metadata=metadata or {},
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        # Store in appropriate layer
        stored = False
        if layer == MemoryLayer.WORKING:
            try:
                await self.working.store(memory)
                stored = True
            except Exception as e:
                logger.warning(f"Failed to store in working memory: {e}")
        elif layer == MemoryLayer.EPISODIC:
            try:
                self.episodic.store(memory)
                stored = True
            except Exception as e:
                logger.warning(f"Failed to store in episodic memory: {e}")
        elif layer == MemoryLayer.SEMANTIC:
            try:
                await self.semantic.store(memory, entities)
                stored = True
            except Exception as e:
                logger.warning(f"Failed to store in semantic memory: {e}")
        elif layer == MemoryLayer.PROCEDURAL:
            try:
                self.procedural.store(memory)
                stored = True
            except Exception as e:
                logger.warning(f"Failed to store in procedural memory: {e}")
        
        if stored:
            logger.debug(f"Stored memory {memory_id} in {layer.value}")
        else:
            logger.warning(f"Could not store memory {memory_id} - layer unavailable")
        
        return memory_id
    
    async def recall(self, query: str, 
                    layers: Optional[List[MemoryLayer]] = None,
                    limit: int = 10) -> List[MemoryEntry]:
        """
        Multi-layer memory retrieval
        Searches across specified layers and merges results
        
        Args:
            query: Search query
            layers: Which layers to search (default: all)
            limit: Maximum results to return
        
        Returns:
            List of matching memories, ranked by relevance
        """
        if layers is None:
            layers = [MemoryLayer.WORKING, MemoryLayer.EPISODIC, 
                     MemoryLayer.SEMANTIC, MemoryLayer.PROCEDURAL]
        
        all_results = []
        
        # Search each layer
        if MemoryLayer.WORKING in layers:
            try:
                results = await self.working.search(query, limit)
                all_results.extend([(r, 1.0) for r in results])  # Boost working memory
            except Exception as e:
                logger.debug(f"Working memory search failed: {e}")
        
        if MemoryLayer.EPISODIC in layers:
            try:
                results = self.episodic.search(query, limit)
                all_results.extend([(r, 0.8) for r in results])
            except Exception as e:
                logger.debug(f"Episodic memory search failed: {e}")
        
        if MemoryLayer.SEMANTIC in layers:
            try:
                results = await self.semantic.search(query, limit)
                all_results.extend([(r, 0.9) for r in results])
            except Exception as e:
                logger.debug(f"Semantic memory search failed: {e}")
        
        if MemoryLayer.PROCEDURAL in layers:
            try:
                results = self.procedural.search(query, limit)
                all_results.extend([(r, 0.7) for r in results])
            except Exception as e:
                logger.debug(f"Procedural memory search failed: {e}")
        
        # Merge and rank by composite score
        seen_ids = set()
        ranked = []
        
        for memory, layer_boost in all_results:
            if memory.id in seen_ids:
                continue
            seen_ids.add(memory.id)
            
            # Calculate composite score
            recency = self._recency_score(memory.last_accessed)
            score = (
                memory.importance * 0.3 +
                min(memory.access_count / 100, 1.0) * 0.2 +
                recency * 0.2 +
                layer_boost * 0.3
            )
            
            ranked.append((score, memory))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[0], reverse=True)
        
        # Update access counts
        for _, memory in ranked[:limit]:
            await self._touch_memory(memory)
        
        return [m for _, m in ranked[:limit]]
    
    async def recall_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory by ID across all layers"""
        # Try layers in order of speed
        memory = await self.working.retrieve(memory_id)
        if memory:
            return memory
        
        memory = self.episodic.retrieve(memory_id)
        if memory:
            # Promote to working
            await self._promote(memory, MemoryLayer.WORKING)
            return memory
        
        memory = await self.semantic.retrieve(memory_id)
        if memory:
            await self._promote(memory, MemoryLayer.WORKING)
            return memory
        
        memory = self.procedural.retrieve(memory_id)
        if memory:
            return memory
        
        return None
    
    async def recall_recent(self, hours: int = 24, limit: int = 50) -> List[MemoryEntry]:
        """Get recent memories from episodic layer"""
        return self.episodic.get_recent(hours, limit)
    
    async def recall_important(self, min_importance: float = 0.7, 
                               limit: int = 20) -> List[MemoryEntry]:
        """Get high-importance memories"""
        return self.episodic.get_by_importance(min_importance, limit)
    
    async def find_related(self, memory_id: str, 
                          depth: int = 2) -> List[Dict]:
        """Find related memories through semantic graph"""
        return await self.semantic.find_related(memory_id, depth)
    
    async def get_pattern(self, situation: str) -> Optional[Dict]:
        """Find matching procedural pattern"""
        return self.procedural.find_matching_pattern(situation)
    
    async def record_pattern_success(self, pattern_id: str, 
                                     success: bool,
                                     **kwargs) -> bool:
        """Record execution result of a pattern"""
        return self.procedural.record_execution(pattern_id, success, **kwargs)
    
    async def promote_to_semantic(self, memory_id: str,
                                  entities: Optional[List[Dict]] = None) -> bool:
        """Promote a memory to semantic layer with entity extraction"""
        memory = await self.recall_by_id(memory_id)
        if not memory:
            return False
        
        return await self._promote(memory, MemoryLayer.SEMANTIC, entities)
    
    async def mark_important(self, memory_id: str) -> bool:
        """Mark a memory as important (user explicit mark)"""
        memory = await self.recall_by_id(memory_id)
        if not memory:
            return False
        
        memory.user_marked = True
        memory.importance = 1.0
        
        # Re-store in current layer
        if memory.layer == MemoryLayer.EPISODIC:
            self.episodic.store(memory)
        elif memory.layer == MemoryLayer.SEMANTIC:
            await self.semantic.store(memory)
        
        return True
    
    async def forget(self, memory_id: str) -> bool:
        """Remove a memory from all layers"""
        results = await asyncio.gather(
            self.working.delete(memory_id),
            asyncio.to_thread(self.episodic.delete, memory_id),
            self.semantic.delete(memory_id),
            asyncio.to_thread(self.procedural.delete, memory_id)
        )
        return any(results)
    
    async def consolidate(self) -> Dict[str, Any]:
        """
        Run consolidation across all layers:
        1. Promote high-importance memories
        2. Demote low-retention memories
        3. Archive old episodic memories
        """
        report = {
            "promoted": 0,
            "demoted": 0,
            "archived": 0,
            "timestamp": time.time()
        }
        
        # Episodic consolidation
        episodic_report = self.episodic.consolidate(days_threshold=30)
        report["archived"] = episodic_report.get("archived", 0)
        
        # TODO: Add promotion/demotion logic based on importance and access patterns
        
        logger.info(f"Consolidation complete: {report}")
        return report
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all layers"""
        working_stats = await self.working.get_stats()
        episodic_stats = self.episodic.get_stats()
        semantic_stats = await self.semantic.get_stats()
        procedural_stats = self.procedural.get_stats()
        
        return {
            "working": working_stats,
            "episodic": episodic_stats,
            "semantic": semantic_stats,
            "procedural": procedural_stats,
            "overall_hit_rate": (
                (working_stats.get("hit_rate", 0) +
                 episodic_stats.get("hit_rate", 0) +
                 semantic_stats.get("hit_rate", 0) +
                 procedural_stats.get("hit_rate", 0)) / 4
            )
        }
    
    # Internal methods
    
    async def _promote(self, memory: MemoryEntry, 
                      to_layer: MemoryLayer,
                      entities: Optional[List[Dict]] = None) -> bool:
        """Promote memory to higher layer"""
        logger.debug(f"Promoting {memory.id} to {to_layer.value}")
        
        if to_layer == MemoryLayer.WORKING:
            await self.working.store(memory)
        elif to_layer == MemoryLayer.SEMANTIC:
            await self.semantic.store(memory, entities)
        
        # Notify callbacks
        for callback in self._promotion_callbacks:
            try:
                await callback(memory, to_layer)
            except Exception as e:
                logger.error(f"Promotion callback failed: {e}")
        
        return True
    
    async def _demote(self, memory: MemoryEntry, 
                     to_layer: MemoryLayer) -> bool:
        """Demote memory to lower layer"""
        logger.debug(f"Demoting {memory.id} to {to_layer.value}")
        
        if to_layer == MemoryLayer.EPISODIC:
            self.episodic.store(memory)
        
        # Notify callbacks
        for callback in self._demotion_callbacks:
            try:
                await callback(memory, to_layer)
            except Exception as e:
                logger.error(f"Demotion callback failed: {e}")
        
        return True
    
    async def _touch_memory(self, memory: MemoryEntry):
        """Update access time and count"""
        memory.access_count += 1
        memory.last_accessed = time.time()
        
        # Update importance
        memory.importance = self.lifecycle.calculate_importance(memory)
    
    def _recency_score(self, timestamp: float) -> float:
        """Calculate recency score (0-1) with exponential decay"""
        days_since = (time.time() - timestamp) / 86400
        return float(__import__('numpy').exp(-days_since / 7))
    
    def on_promotion(self, callback: Callable):
        """Register callback for memory promotion"""
        self._promotion_callbacks.append(callback)
    
    def on_demotion(self, callback: Callable):
        """Register callback for memory demotion"""
        self._demotion_callbacks.append(callback)
