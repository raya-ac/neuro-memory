#!/usr/bin/env python3
"""
Semantic Memory Layer - Neo4j-based knowledge graph
Target latency: < 20ms
Entity extraction and relationship tracking
"""

import json
import time
from typing import List, Optional, Dict, Any, Set
from neo4j import AsyncGraphDatabase
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import AbstractMemoryLayer, MemoryEntry, MemoryLayer
import logging

logger = logging.getLogger("neuro-memory.semantic")


class SemanticMemoryLayer(AbstractMemoryLayer):
    """
    L3: Semantic Memory - Knowledge graph with entities and relationships
    - Neo4j storage
    - Entity extraction
    - Relationship tracking
    - Multi-hop reasoning
    """
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 user: str = None, password: str = None):
        super().__init__(MemoryLayer.SEMANTIC)
        self.uri = neo4j_uri
        self.auth = (user, password) if user and password else None
        self._driver = None
    
    async def connect(self):
        """Initialize Neo4j connection"""
        try:
            self._driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)
            await self._driver.verify_connectivity()
            await self._create_constraints()
            logger.info("Semantic memory connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def disconnect(self):
        """Close Neo4j connection"""
        if self._driver:
            await self._driver.close()
    
    async def _create_constraints(self):
        """Create graph constraints (Neo4j 4.0.x syntax)"""
        async with self._driver.session() as session:
            # Constraints - Neo4j 4.0.x syntax (no IF NOT EXISTS)
            constraints = [
                "CREATE CONSTRAINT ON (m:Memory) ASSERT m.id IS UNIQUE",
                "CREATE CONSTRAINT ON (e:Entity) ASSERT e.canonical IS UNIQUE"
            ]
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception as e:
                    # Ignore if already exists
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Constraint creation issue: {e}")
            
            # Indexes - Neo4j 4.0.x syntax
            indexes = [
                "CREATE INDEX ON :Memory(importance)",
                "CREATE INDEX ON :Memory(created_at)",
                "CREATE INDEX ON :Entity(type)"
            ]
            for index in indexes:
                try:
                    await session.run(index)
                except Exception as e:
                    # Ignore if already exists
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index creation issue: {e}")
    
    async def store(self, memory: MemoryEntry, 
                   entities: Optional[List[Dict]] = None) -> bool:
        """
        Store memory in semantic layer with optional entity extraction
        """
        start = time.time()
        
        try:
            async with self._driver.session() as session:
                # Create Memory node
                await session.run(
                    """
                    MERGE (m:Memory {id: $id})
                    SET m.content = $content,
                        m.importance = $importance,
                        m.created_at = $created_at,
                        m.last_accessed = $last_accessed,
                        m.access_count = $access_count
                    """,
                    {
                        'id': memory.id,
                        'content': memory.content,
                        'importance': memory.importance,
                        'created_at': memory.created_at,
                        'last_accessed': memory.last_accessed,
                        'access_count': memory.access_count
                    }
                )
                
                # Create entities and relationships
                if entities:
                    for entity in entities:
                        await self._link_entity(session, memory.id, entity)
                
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=True)
                return True
                
        except Exception as e:
            logger.error(f"Failed to store in semantic memory: {e}")
            return False
    
    async def _link_entity(self, session, memory_id: str, entity: Dict):
        """Link memory to entity with relationship"""
        entity_name = entity.get('name', '')
        entity_type = entity.get('type', 'concept')
        confidence = entity.get('confidence', 0.5)
        
        await session.run(
            """
            MERGE (e:Entity {canonical: $canonical})
            SET e.name = $name,
                e.type = $type,
                e.first_seen = COALESCE(e.first_seen, $now),
                e.mention_count = COALESCE(e.mention_count, 0) + 1
            
            WITH e
            MATCH (m:Memory {id: $memory_id})
            MERGE (m)-[r:MENTIONS]->(e)
            SET r.confidence = $confidence,
                r.mentioned_at = $now
            """,
            {
                'canonical': entity_name.lower().replace(' ', '_'),
                'name': entity_name,
                'type': entity_type,
                'memory_id': memory_id,
                'confidence': confidence,
                'now': time.time()
            }
        )
    
    async def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve memory from graph"""
        start = time.time()
        
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (m:Memory {id: $id})
                    SET m.access_count = COALESCE(m.access_count, 0) + 1,
                        m.last_accessed = $now
                    RETURN m
                    """,
                    {'id': memory_id, 'now': time.time()}
                )
                
                record = await result.single()
                
                if record:
                    node = record['m']
                    memory = MemoryEntry(
                        id=node['id'],
                        content=node['content'],
                        layer=MemoryLayer.SEMANTIC,
                        importance=node.get('importance', 0.5),
                        access_count=node.get('access_count', 0),
                        created_at=node.get('created_at', time.time()),
                        last_accessed=node.get('last_accessed', time.time())
                    )
                    
                    latency = (time.time() - start) * 1000
                    self.record_stat(latency, hit=True)
                    return memory
                
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=False)
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve from semantic memory: {e}")
            return None
    
    async def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search semantic memory using text match"""
        start = time.time()
        results = []
        
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (m:Memory)
                    WHERE m.content CONTAINS $query
                    RETURN m
                    ORDER BY m.importance DESC, m.last_accessed DESC
                    LIMIT $limit
                    """,
                    {'query': query, 'limit': limit}
                )
                
                async for record in result:
                    node = record['m']
                    results.append(MemoryEntry(
                        id=node['id'],
                        content=node['content'],
                        layer=MemoryLayer.SEMANTIC,
                        importance=node.get('importance', 0.5),
                        created_at=node.get('created_at', time.time()),
                        last_accessed=node.get('last_accessed', time.time())
                    ))
                
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=len(results) > 0)
                
        except Exception as e:
            logger.error(f"Search failed in semantic memory: {e}")
        
        return results
    
    async def find_related(self, memory_id: str, depth: int = 2) -> List[Dict]:
        """
        Find related memories through graph traversal
        Multi-hop reasoning
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH path = (m:Memory {id: $id})-[:MENTIONS|RELATES_TO*1..$depth]-(related:Memory)
                    WHERE related.id <> $id
                    RETURN related, length(path) as distance
                    ORDER BY distance, related.importance DESC
                    LIMIT 20
                    """,
                    {'id': memory_id, 'depth': depth}
                )
                
                related = []
                async for record in result:
                    node = record['related']
                    related.append({
                        'memory': MemoryEntry(
                            id=node['id'],
                            content=node['content'],
                            layer=MemoryLayer.SEMANTIC,
                            importance=node.get('importance', 0.5)
                        ),
                        'distance': record['distance']
                    })
                
                return related
                
        except Exception as e:
            logger.error(f"Failed to find related memories: {e}")
            return []
    
    async def connect_memories(self, from_id: str, to_id: str, 
                               relation: str = "RELATES_TO") -> bool:
        """Create relationship between two memories"""
        try:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Memory {id: $from_id}), (b:Memory {id: $to_id})
                    MERGE (a)-[r:$relation]->(b)
                    SET r.created_at = $now
                    """,
                    {
                        'from_id': from_id,
                        'to_id': to_id,
                        'relation': relation,
                        'now': time.time()
                    }
                )
                return True
        except Exception as e:
            logger.error(f"Failed to connect memories: {e}")
            return False
    
    async def get_entities(self, memory_id: str) -> List[Dict]:
        """Get entities mentioned in a memory"""
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (m:Memory {id: $id})-[r:MENTIONS]->(e:Entity)
                    RETURN e, r.confidence as confidence
                    ORDER BY r.confidence DESC
                    """,
                    {'id': memory_id}
                )
                
                entities = []
                async for record in result:
                    node = record['e']
                    entities.append({
                        'name': node['name'],
                        'type': node['type'],
                        'confidence': record['confidence'],
                        'mention_count': node.get('mention_count', 1)
                    })
                
                return entities
                
        except Exception as e:
            logger.error(f"Failed to get entities: {e}")
            return []
    
    async def get_central_entities(self, limit: int = 20) -> List[Dict]:
        """Get most frequently mentioned entities (graph centrality)"""
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity)<-[:MENTIONS]-(m:Memory)
                    WITH e, count(m) as mentions
                    ORDER BY mentions DESC
                    LIMIT $limit
                    RETURN e.name as name, e.type as type, mentions
                    """,
                    {'limit': limit}
                )
                
                entities = []
                async for record in result:
                    entities.append({
                        'name': record['name'],
                        'type': record['type'],
                        'mentions': record['mentions']
                    })
                
                return entities
                
        except Exception as e:
            logger.error(f"Failed to get central entities: {e}")
            return []
    
    async def delete(self, memory_id: str) -> bool:
        """Remove memory from graph"""
        try:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MATCH (m:Memory {id: $id})
                    DETACH DELETE m
                    """,
                    {'id': memory_id}
                )
                return True
        except Exception as e:
            logger.error(f"Failed to delete from semantic memory: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get semantic memory statistics"""
        try:
            async with self._driver.session() as session:
                # Memory count
                result = await session.run("MATCH (m:Memory) RETURN count(m) as count")
                record = await result.single()
                memory_count = record['count'] if record else 0
                
                # Entity count
                result = await session.run("MATCH (e:Entity) RETURN count(e) as count")
                record = await result.single()
                entity_count = record['count'] if record else 0
                
                # Relationship count
                result = await session.run("MATCH ()-[r]-() RETURN count(r) as count")
                record = await result.single()
                rel_count = record['count'] if record else 0
                
                return {
                    "memories": memory_count,
                    "entities": entity_count,
                    "relationships": rel_count,
                    "hit_rate": self.hit_rate,
                    "avg_latency_ms": self.avg_latency_ms
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
