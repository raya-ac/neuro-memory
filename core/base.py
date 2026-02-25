#!/usr/bin/env python3
"""
NeuroMemoryManager - 4-Layer Cognitive Memory Architecture
Implements hierarchical memory with predictive caching and knowledge graphs
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set
import numpy as np
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neuro-memory")


class MemoryLayer(Enum):
    """The four layers of cognitive memory"""
    WORKING = "working"      # Hot cache - Redis
    EPISODIC = "episodic"    # Recent events - SQLite
    SEMANTIC = "semantic"    # Knowledge graph - Neo4j
    PROCEDURAL = "procedural"  # Patterns - SQLite


@dataclass
class MemoryEntry:
    """Universal memory container"""
    id: str
    content: str
    layer: MemoryLayer
    embedding: Optional[List[float]] = None
    importance: float = 0.5
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    emotional_valence: float = 0.0
    task_criticality: float = 0.0
    user_marked: bool = False
    archived: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    summary_of: Optional[str] = None  # Points to summarized memories
    
    # Forgetting curve parameters
    stability: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'content': self.content,
            'layer': self.layer.value,
            'embedding': self.embedding,
            'importance': self.importance,
            'access_count': self.access_count,
            'created_at': self.created_at,
            'last_accessed': self.last_accessed,
            'emotional_valence': self.emotional_valence,
            'task_criticality': self.task_criticality,
            'user_marked': self.user_marked,
            'archived': self.archived,
            'metadata': self.metadata,
            'summary_of': self.summary_of,
            'stability': self.stability
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        data = data.copy()
        data['layer'] = MemoryLayer(data['layer'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MemoryLifecycle:
    """Manages importance scoring and forgetting curves"""
    
    @staticmethod
    def calculate_importance(memory: MemoryEntry) -> float:
        """Composite importance scoring"""
        # Access frequency (normalized)
        access_freq = min(memory.access_count / 100, 1.0) * 0.20
        
        # Recency boost (exponential decay over 30 days)
        days_since = (time.time() - memory.last_accessed) / 86400
        recency = np.exp(-days_since / 7) * 0.15
        
        # User explicit mark
        user_mark = (1.0 if memory.user_marked else 0.0) * 0.15
        
        # Task criticality
        task_crit = memory.task_criticality * 0.10
        
        # Emotional valence (absolute value)
        emotional = abs(memory.emotional_valence) * 0.10
        
        # Graph centrality (placeholder - would query Neo4j)
        centrality = memory.metadata.get('graph_centrality', 0.5) * 0.10
        
        # Semantic importance (from embedding quality)
        semantic = (1.0 if memory.embedding else 0.0) * 0.20
        
        return min(access_freq + recency + user_mark + task_crit + emotional + centrality + semantic, 1.0)
    
    @staticmethod
    def retention_probability(memory: MemoryEntry) -> float:
        """Ebbinghaus forgetting curve"""
        days_since_access = (time.time() - memory.last_accessed) / 86400
        # Stability increases with importance and access count
        stability = 1 + (memory.importance * 10) + (memory.access_count * 2)
        return np.exp(-days_since_access / stability)
    
    @staticmethod
    def should_promote(memory: MemoryEntry) -> bool:
        """Check if memory should move to higher layer"""
        if memory.layer == MemoryLayer.EPISODIC and memory.importance > 0.7:
            return True
        if memory.layer == MemoryLayer.SEMANTIC and memory.access_count > 50:
            return True
        return False
    
    @staticmethod
    def should_demote(memory: MemoryEntry) -> bool:
        """Check if memory should move to lower layer"""
        retention = MemoryLifecycle.retention_probability(memory)
        if memory.layer == MemoryLayer.WORKING and retention < 0.3:
            return True
        if memory.layer == MemoryLayer.SEMANTIC and memory.importance < 0.3:
            return True
        return False


class AbstractMemoryLayer(ABC):
    """Base class for all memory layers"""
    
    def __init__(self, layer_type: MemoryLayer):
        self.layer_type = layer_type
        self.stats = {'queries': 0, 'hits': 0, 'latency_ms': []}
    
    @abstractmethod
    async def store(self, memory: MemoryEntry) -> bool:
        pass
    
    @abstractmethod
    async def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        pass
    
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        pass
    
    def record_stat(self, latency_ms: float, hit: bool = True):
        self.stats['queries'] += 1
        if hit:
            self.stats['hits'] += 1
        self.stats['latency_ms'].append(latency_ms)
        # Keep last 1000 measurements
        if len(self.stats['latency_ms']) > 1000:
            self.stats['latency_ms'] = self.stats['latency_ms'][-1000:]
    
    @property
    def hit_rate(self) -> float:
        if self.stats['queries'] == 0:
            return 0.0
        return self.stats['hits'] / self.stats['queries']
    
    @property
    def avg_latency_ms(self) -> float:
        if not self.stats['latency_ms']:
            return 0.0
        return sum(self.stats['latency_ms']) / len(self.stats['latency_ms'])
