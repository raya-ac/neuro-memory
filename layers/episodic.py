#!/usr/bin/env python3
"""
Episodic Memory Layer - SQLite-based recent event storage
Target latency: < 10ms
90-day retention with auto-summarization
"""

import sqlite3
import json
import time
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import AbstractMemoryLayer, MemoryEntry, MemoryLayer, MemoryLifecycle
import logging

logger = logging.getLogger("neuro-memory.episodic")


class EpisodicMemoryLayer(AbstractMemoryLayer):
    """
    L2: Episodic Memory - Recent events and experiences
    - SQLite storage
    - 90-day retention
    - Auto-summarization
    - Emotional tagging
    """
    
    def __init__(self, db_path: str = "/root/.openclaw/memory-system/episodic.db"):
        super().__init__(MemoryLayer.EPISODIC)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lifecycle = MemoryLifecycle()
    
    def connect(self):
        """Initialize SQLite connection"""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Episodic memory connected")
    
    def disconnect(self):
        """Close SQLite connection"""
        if self._conn:
            self._conn.close()
    
    def _create_tables(self):
        """Create enhanced schema"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding BLOB,
                layer TEXT DEFAULT 'episodic',
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                last_accessed REAL,
                emotional_valence REAL DEFAULT 0.0,
                task_criticality REAL DEFAULT 0.0,
                user_marked BOOLEAN DEFAULT 0,
                archived BOOLEAN DEFAULT 0,
                metadata TEXT,
                summary_of TEXT,
                stability REAL DEFAULT 1.0
            );
            
            CREATE INDEX IF NOT EXISTS idx_memories_temporal 
                ON memories(created_at, last_accessed);
            
            CREATE INDEX IF NOT EXISTS idx_memories_importance 
                ON memories(importance DESC);
            
            CREATE INDEX IF NOT EXISTS idx_memories_access 
                ON memories(last_accessed DESC);
            
            CREATE INDEX IF NOT EXISTS idx_memories_layer 
                ON memories(layer) WHERE layer = 'episodic';
            
            -- Embedding cache with model versioning
            CREATE TABLE IF NOT EXISTS embedding_cache (
                content_hash TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                model_version TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            
            -- Access log for pattern detection
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                accessed_at REAL NOT NULL,
                query TEXT,
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_access_memory 
                ON access_log(memory_id, accessed_at);
        """)
        self._conn.commit()
    
    def store(self, memory: MemoryEntry) -> bool:
        """Store memory in episodic layer"""
        start = time.time()
        
        try:
            # Calculate importance before storing
            memory.importance = self._lifecycle.calculate_importance(memory)
            
            cursor = self._conn.execute(
                """INSERT OR REPLACE INTO memories 
                   (id, content, embedding, layer, importance, access_count,
                    created_at, last_accessed, emotional_valence, task_criticality,
                    user_marked, archived, metadata, summary_of, stability)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory.id,
                    memory.content,
                    json.dumps(memory.embedding) if memory.embedding else None,
                    memory.layer.value,
                    memory.importance,
                    memory.access_count,
                    memory.created_at,
                    memory.last_accessed,
                    memory.emotional_valence,
                    memory.task_criticality,
                    memory.user_marked,
                    memory.archived,
                    json.dumps(memory.metadata),
                    memory.summary_of,
                    memory.stability
                )
            )
            self._conn.commit()
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store in episodic memory: {e}")
            return False
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve from episodic layer"""
        start = time.time()
        
        try:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ? AND layer = 'episodic'",
                (memory_id,)
            ).fetchone()
            
            if row:
                # Update access count and time
                self._conn.execute(
                    """UPDATE memories 
                       SET access_count = access_count + 1, 
                           last_accessed = ?
                       WHERE id = ?""",
                    (time.time(), memory_id)
                )
                self._conn.commit()
                
                # Log access
                self._conn.execute(
                    "INSERT INTO access_log (memory_id, accessed_at) VALUES (?, ?)",
                    (memory_id, time.time())
                )
                self._conn.commit()
                
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=True)
                return self._row_to_entry(row)
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=False)
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve from episodic memory: {e}")
            return None
    
    def search(self, query: str, limit: int = 10, 
               recency_weight: float = 0.3) -> List[MemoryEntry]:
        """
        Search episodic memory with recency bias
        """
        start = time.time()
        results = []
        
        try:
            # Get recent memories with text match
            cursor = self._conn.execute(
                """SELECT * FROM memories 
                   WHERE layer = 'episodic' 
                   AND content LIKE ?
                   AND archived = 0
                   ORDER BY last_accessed DESC
                   LIMIT ?""",
                (f"%{query}%", limit * 2)
            )
            
            rows = cursor.fetchall()
            scored_results = []
            
            for row in rows:
                memory = self._row_to_entry(row)
                
                # Score based on text match + recency + importance
                text_score = 1.0 if query.lower() in memory.content.lower() else 0.5
                
                days_since = (time.time() - memory.last_accessed) / 86400
                recency_score = np.exp(-days_since / 30)  # 30-day half-life
                
                total_score = (
                    text_score * 0.4 +
                    recency_score * recency_weight +
                    memory.importance * 0.3
                )
                
                scored_results.append((total_score, memory))
            
            # Sort by score and return top results
            scored_results.sort(key=lambda x: x[0], reverse=True)
            results = [m for _, m in scored_results[:limit]]
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=len(results) > 0)
            
        except Exception as e:
            logger.error(f"Search failed in episodic memory: {e}")
        
        return results
    
    def get_recent(self, hours: int = 24, limit: int = 50) -> List[MemoryEntry]:
        """Get recent memories"""
        since = time.time() - (hours * 3600)
        
        cursor = self._conn.execute(
            """SELECT * FROM memories 
               WHERE layer = 'episodic' 
               AND created_at > ?
               AND archived = 0
               ORDER BY created_at DESC
               LIMIT ?""",
            (since, limit)
        )
        
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def get_by_importance(self, min_importance: float = 0.7, 
                         limit: int = 20) -> List[MemoryEntry]:
        """Get high-importance memories"""
        cursor = self._conn.execute(
            """SELECT * FROM memories 
               WHERE layer = 'episodic' 
               AND importance >= ?
               AND archived = 0
               ORDER BY importance DESC, last_accessed DESC
               LIMIT ?""",
            (min_importance, limit)
        )
        
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def delete(self, memory_id: str) -> bool:
        """Soft delete (archive) memory"""
        try:
            self._conn.execute(
                "UPDATE memories SET archived = 1 WHERE id = ?",
                (memory_id,)
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from episodic memory: {e}")
            return False
    
    def consolidate(self, days_threshold: int = 30) -> Dict[str, Any]:
        """
        Nightly consolidation:
        1. Deduplicate similar memories
        2. Summarize old episodic memories
        3. Archive low-importance memories
        """
        report = {"deduplicated": 0, "summarized": 0, "archived": 0}
        
        try:
            cutoff = time.time() - (days_threshold * 86400)
            
            # Find old, low-importance memories
            cursor = self._conn.execute(
                """SELECT id FROM memories 
                   WHERE layer = 'episodic'
                   AND created_at < ?
                   AND importance < 0.3
                   AND access_count < 3
                   AND archived = 0""",
                (cutoff,)
            )
            
            to_archive = [row[0] for row in cursor.fetchall()]
            
            # Archive them
            for mid in to_archive:
                self._conn.execute(
                    "UPDATE memories SET archived = 1 WHERE id = ?",
                    (mid,)
                )
            
            report["archived"] = len(to_archive)
            self._conn.commit()
            
            logger.info(f"Consolidation complete: {report}")
            
        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
        
        return report
    
    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert database row to MemoryEntry"""
        data = dict(row)
        
        # Parse JSON fields
        if data.get('embedding'):
            data['embedding'] = json.loads(data['embedding'])
        if data.get('metadata'):
            data['metadata'] = json.loads(data['metadata'])
        
        # Convert layer string to enum
        data['layer'] = MemoryLayer(data['layer'])
        
        # Convert booleans
        data['user_marked'] = bool(data['user_marked'])
        data['archived'] = bool(data['archived'])
        
        return MemoryEntry(**{k: v for k, v in data.items() 
                             if k in MemoryEntry.__dataclass_fields__})
    
    def get_stats(self) -> Dict[str, Any]:
        """Get episodic memory statistics"""
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE layer = 'episodic'"
            ).fetchone()[0]
            
            active = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE layer = 'episodic' AND archived = 0"
            ).fetchone()[0]
            
            high_importance = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE layer = 'episodic' AND importance > 0.7"
            ).fetchone()[0]
            
            recent_24h = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE layer = 'episodic' AND created_at > ?",
                (time.time() - 86400,)
            ).fetchone()[0]
            
            return {
                "total_memories": total,
                "active_memories": active,
                "archived": total - active,
                "high_importance": high_importance,
                "created_24h": recent_24h,
                "hit_rate": self.hit_rate,
                "avg_latency_ms": self.avg_latency_ms
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
