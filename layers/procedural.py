#!/usr/bin/env python3
"""
Procedural Memory Layer - Pattern compilation and success tracking
Target latency: < 5ms
Stores successful patterns and procedures
"""

import sqlite3
import json
import time
import hashlib
from typing import List, Optional, Dict, Any, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import AbstractMemoryLayer, MemoryEntry, MemoryLayer
import logging

logger = logging.getLogger("neuro-memory.procedural")


class ProceduralMemoryLayer(AbstractMemoryLayer):
    """
    L4: Procedural Memory - Compiled patterns and successful procedures
    - SQLite storage
    - Pattern templates
    - Success tracking
    - Parameter matching
    """
    
    def __init__(self, db_path: str = "/root/.openclaw/memory-system/procedural.db"):
        super().__init__(MemoryLayer.PROCEDURAL)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Initialize SQLite connection"""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Procedural memory connected")
    
    def disconnect(self):
        """Close SQLite connection"""
        if self._conn:
            self._conn.close()
    
    def _create_tables(self):
        """Create procedural memory schema"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS procedures (
                id TEXT PRIMARY KEY,
                pattern_template TEXT NOT NULL,
                description TEXT,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_success REAL,
                last_failure REAL,
                avg_execution_time_ms REAL,
                parameters TEXT,  -- JSON schema for parameters
                tags TEXT,  -- JSON array
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_procedures_success 
                ON procedures(success_count DESC);
            
            CREATE INDEX IF NOT EXISTS idx_procedures_tags 
                ON procedures(tags);
            
            -- Pattern execution log
            CREATE TABLE IF NOT EXISTS procedure_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                procedure_id TEXT NOT NULL,
                parameters TEXT,  -- JSON
                success BOOLEAN,
                execution_time_ms REAL,
                error_message TEXT,
                executed_at REAL NOT NULL,
                FOREIGN KEY (procedure_id) REFERENCES procedures(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_executions_procedure 
                ON procedure_executions(procedure_id, executed_at);
            
            -- Pattern library for common operations
            CREATE TABLE IF NOT EXISTS pattern_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pattern_type TEXT,  -- 'debug', 'refactor', 'deploy', etc.
                template TEXT NOT NULL,
                example_inputs TEXT,  -- JSON
                example_outputs TEXT,  -- JSON
                use_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0
            );
        """)
        self._conn.commit()
    
    def store(self, memory: MemoryEntry) -> bool:
        """
        Store a successful pattern as procedural memory
        """
        start = time.time()
        
        try:
            # Extract pattern from memory content
            pattern_data = self._extract_pattern(memory)
            
            cursor = self._conn.execute(
                """INSERT OR REPLACE INTO procedures 
                   (id, pattern_template, description, parameters, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory.id,
                    pattern_data.get('template', memory.content),
                    memory.metadata.get('description', ''),
                    json.dumps(pattern_data.get('parameters', {})),
                    json.dumps(memory.metadata.get('tags', [])),
                    memory.created_at,
                    time.time()
                )
            )
            self._conn.commit()
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store in procedural memory: {e}")
            return False
    
    def _extract_pattern(self, memory: MemoryEntry) -> Dict:
        """Extract pattern template from memory content"""
        content = memory.content
        
        # Simple pattern extraction - can be enhanced with NLP
        pattern = {
            'template': content,
            'parameters': {},
            'type': memory.metadata.get('pattern_type', 'general')
        }
        
        # Detect common patterns
        if 'error' in content.lower() and 'fix' in content.lower():
            pattern['type'] = 'debug'
            pattern['parameters'] = {'error_type': 'string', 'solution': 'string'}
        
        elif 'deploy' in content.lower() or 'release' in content.lower():
            pattern['type'] = 'deploy'
            pattern['parameters'] = {'service': 'string', 'version': 'string'}
        
        elif 'refactor' in content.lower():
            pattern['type'] = 'refactor'
            pattern['parameters'] = {'target': 'string', 'reason': 'string'}
        
        return pattern
    
    def retrieve(self, pattern_id: str) -> Optional[MemoryEntry]:
        """Retrieve a procedure by ID"""
        start = time.time()
        
        try:
            row = self._conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (pattern_id,)
            ).fetchone()
            
            if row:
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=True)
                return self._row_to_entry(row)
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=False)
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve from procedural memory: {e}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search procedures by description or template"""
        start = time.time()
        results = []
        
        try:
            cursor = self._conn.execute(
                """SELECT * FROM procedures 
                   WHERE description LIKE ? 
                   OR pattern_template LIKE ?
                   OR tags LIKE ?
                   ORDER BY success_count DESC, updated_at DESC
                   LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit)
            )
            
            results = [self._row_to_entry(row) for row in cursor.fetchall()]
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=len(results) > 0)
            
        except Exception as e:
            logger.error(f"Search failed in procedural memory: {e}")
        
        return results
    
    def find_matching_pattern(self, situation: str) -> Optional[Dict]:
        """Find best matching pattern for a situation"""
        try:
            # Get all patterns
            cursor = self._conn.execute(
                """SELECT * FROM procedures 
                   ORDER BY success_count DESC, updated_at DESC"""
            )
            
            best_match = None
            best_score = 0
            
            for row in cursor.fetchall():
                pattern = row['pattern_template']
                
                # Simple word overlap scoring
                pattern_words = set(pattern.lower().split())
                situation_words = set(situation.lower().split())
                
                if pattern_words:
                    overlap = len(pattern_words & situation_words)
                    score = overlap / len(pattern_words)
                    
                    # Boost by success rate
                    total = row['success_count'] + row['failure_count']
                    if total > 0:
                        success_rate = row['success_count'] / total
                        score *= (0.5 + 0.5 * success_rate)  # Weight success
                    
                    if score > best_score and score > 0.3:  # Threshold
                        best_score = score
                        best_match = {
                            'id': row['id'],
                            'pattern': pattern,
                            'description': row['description'],
                            'success_count': row['success_count'],
                            'match_score': score
                        }
            
            return best_match
            
        except Exception as e:
            logger.error(f"Pattern matching failed: {e}")
            return None
    
    def record_execution(self, procedure_id: str, success: bool,
                        parameters: Optional[Dict] = None,
                        execution_time_ms: Optional[float] = None,
                        error_message: Optional[str] = None) -> bool:
        """Record execution result of a procedure"""
        try:
            # Log execution
            self._conn.execute(
                """INSERT INTO procedure_executions 
                   (procedure_id, parameters, success, execution_time_ms, error_message, executed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    procedure_id,
                    json.dumps(parameters) if parameters else None,
                    success,
                    execution_time_ms,
                    error_message,
                    time.time()
                )
            )
            
            # Update procedure stats
            if success:
                self._conn.execute(
                    """UPDATE procedures 
                       SET success_count = success_count + 1,
                           last_success = ?,
                           avg_execution_time_ms = (
                               (COALESCE(avg_execution_time_ms, 0) * success_count + ?) / 
                               (success_count + 1)
                           ),
                           updated_at = ?
                       WHERE id = ?""",
                    (time.time(), execution_time_ms or 0, time.time(), procedure_id)
                )
            else:
                self._conn.execute(
                    """UPDATE procedures 
                       SET failure_count = failure_count + 1,
                           last_failure = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    (time.time(), time.time(), procedure_id)
                )
            
            self._conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to record execution: {e}")
            return False
    
    def get_successful_patterns(self, min_successes: int = 3,
                                limit: int = 20) -> List[Dict]:
        """Get most successful patterns"""
        try:
            cursor = self._conn.execute(
                """SELECT *, 
                   (success_count * 1.0 / NULLIF(success_count + failure_count, 0)) as success_rate
                   FROM procedures 
                   WHERE success_count >= ?
                   ORDER BY success_rate DESC, success_count DESC
                   LIMIT ?""",
                (min_successes, limit)
            )
            
            patterns = []
            for row in cursor.fetchall():
                patterns.append({
                    'id': row['id'],
                    'template': row['pattern_template'],
                    'description': row['description'],
                    'success_count': row['success_count'],
                    'failure_count': row['failure_count'],
                    'success_rate': row['success_rate'],
                    'avg_execution_time_ms': row['avg_execution_time_ms']
                })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to get successful patterns: {e}")
            return []
    
    def delete(self, pattern_id: str) -> bool:
        """Remove a procedure"""
        try:
            self._conn.execute(
                "DELETE FROM procedures WHERE id = ?",
                (pattern_id,)
            )
            self._conn.execute(
                "DELETE FROM procedure_executions WHERE procedure_id = ?",
                (pattern_id,)
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from procedural memory: {e}")
            return False
    
    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert database row to MemoryEntry"""
        return MemoryEntry(
            id=row['id'],
            content=row['pattern_template'],
            layer=MemoryLayer.PROCEDURAL,
            importance=min(row['success_count'] / 10, 1.0) if row['success_count'] else 0.5,
            access_count=row['success_count'] + row['failure_count'],
            created_at=row['created_at'],
            last_accessed=row['updated_at'],
            metadata={
                'description': row['description'],
                'parameters': json.loads(row['parameters']) if row['parameters'] else {},
                'tags': json.loads(row['tags']) if row['tags'] else []
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get procedural memory statistics"""
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM procedures"
            ).fetchone()[0]
            
            total_executions = self._conn.execute(
                "SELECT COUNT(*) FROM procedure_executions"
            ).fetchone()[0]
            
            success_count = self._conn.execute(
                "SELECT COUNT(*) FROM procedure_executions WHERE success = 1"
            ).fetchone()[0]
            
            return {
                "total_patterns": total,
                "total_executions": total_executions,
                "successful_executions": success_count,
                "success_rate": success_count / total_executions if total_executions > 0 else 0,
                "hit_rate": self.hit_rate,
                "avg_latency_ms": self.avg_latency_ms
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
