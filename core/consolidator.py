#!/usr/bin/env python3
"""
Smart Consolidator - Intelligent memory consolidation
Clustering, summarization, and importance scoring
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("neuro-memory.consolidator")

# Paths
MEMORY_SYSTEM_DIR = Path("/root/.openclaw/memory-system")
EPISODIC_DB = MEMORY_SYSTEM_DIR / "episodic.db"


@dataclass
class MemoryCluster:
    """Cluster of similar memories"""
    centroid_id: str
    member_ids: List[str]
    topic: str
    avg_importance: float
    total_access_count: int


class SmartConsolidator:
    """Intelligent memory consolidation with clustering and scoring"""

    def __init__(self, episodic_db: str = None):
        self.db_path = Path(episodic_db or EPISODIC_DB)
        self._embeddings_available = self._check_embeddings()

    def _check_embeddings(self) -> bool:
        """Check if embeddings are available"""
        try:
            from layers.embeddings import generate_embedding
            test = generate_embedding("test")
            return test is not None
        except:
            return False

    def run_consolidation(self) -> Dict:
        """Run full consolidation cycle"""
        results = {
            'archived': 0,
            'clustered': 0,
            'summarized': 0,
            'scored': 0,
            'promoted': 0
        }

        # 1. Archive old, low-importance memories
        results['archived'] = self._archive_old_memories()

        # 2. Cluster similar memories (if embeddings available)
        if self._embeddings_available:
            clusters = self._cluster_memories()
            results['clustered'] = len(clusters)

            # 3. Summarize large clusters
            for cluster in clusters:
                if len(cluster.member_ids) > 5:
                    self._summarize_cluster(cluster)
                    results['summarized'] += 1

        # 4. Update importance scores
        results['scored'] = self._update_importance_scores()

        # 5. Promote high-value memories to semantic
        results['promoted'] = self._promote_to_semantic()

        return results

    def _archive_old_memories(self, days: int = 90, min_importance: float = 0.3) -> int:
        """Archive memories older than threshold with low importance"""
        cutoff = (datetime.now() - timedelta(days=days)).timestamp()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE memories 
            SET archived = 1 
            WHERE created_at < ? 
            AND importance < ? 
            AND archived = 0
            AND access_count < 3
        """, (cutoff, min_importance))

        archived = cursor.rowcount
        conn.commit()
        conn.close()

        if archived > 0:
            logger.info(f"Archived {archived} old low-importance memories")

        return archived

    def _cluster_memories(self, similarity_threshold: float = 0.8) -> List[MemoryCluster]:
        """Cluster similar memories based on embeddings"""
        from layers.embeddings import generate_embedding, cosine_similarity, EmbeddingIndex

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get unarchived memories with content
        cursor.execute("""
            SELECT id, content, importance, access_count
            FROM memories 
            WHERE archived = 0
            AND content IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 500
        """)

        memories = cursor.fetchall()
        conn.close()

        if not memories:
            return []

        # Build embedding index
        index = EmbeddingIndex()
        memory_map = {}

        for id, content, importance, access_count in memories:
            emb = generate_embedding(content)
            if emb is not None:
                index.add(id, emb)
                memory_map[id] = {
                    'content': content,
                    'importance': importance,
                    'access_count': access_count
                }

        # Find clusters
        clusters = []
        clustered_ids = set()

        for id, mem_data in memory_map.items():
            if id in clustered_ids:
                continue

            # Find similar memories
            query_emb = generate_embedding(mem_data['content'])
            if query_emb is None:
                continue

            similar = index.search(query_emb, k=10)
            similar_ids = [s[0] for s in similar if s[1] >= similarity_threshold]

            if len(similar_ids) > 1:
                # Create cluster
                cluster = MemoryCluster(
                    centroid_id=id,
                    member_ids=similar_ids,
                    topic=self._extract_topic([memory_map[s]['content'] for s in similar_ids if s in memory_map]),
                    avg_importance=sum(memory_map[s]['importance'] for s in similar_ids if s in memory_map) / len(similar_ids),
                    total_access_count=sum(memory_map[s]['access_count'] for s in similar_ids if s in memory_map)
                )
                clusters.append(cluster)
                clustered_ids.update(similar_ids)

        logger.info(f"Found {len(clusters)} memory clusters")
        return clusters

    def _extract_topic(self, contents: List[str]) -> str:
        """Extract common topic from contents"""
        # Simple approach: find common words
        from collections import Counter
        import re

        # Get all words
        words = []
        for content in contents:
            words.extend(re.findall(r'\b[a-z]{4,}\b', content.lower()))

        # Find most common meaningful words
        stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they', 'their', 'what', 'when', 'where', 'which', 'about'}
        filtered = [w for w in words if w not in stop_words]

        if not filtered:
            return "general"

        most_common = Counter(filtered).most_common(3)
        return ', '.join([w for w, _ in most_common])

    def _summarize_cluster(self, cluster: MemoryCluster) -> Optional[str]:
        """Summarize a cluster of memories into one representative memory"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all content from cluster
        placeholders = ','.join('?' * len(cluster.member_ids))
        cursor.execute(f"""
            SELECT content FROM memories 
            WHERE id IN ({placeholders})
        """, cluster.member_ids)

        contents = [row[0] for row in cursor.fetchall()]

        if not contents:
            conn.close()
            return None

        # Create summary memory
        summary = f"[Cluster: {cluster.topic}]\n{len(contents)} related memories consolidated."

        # Store summary
        cursor.execute("""
            INSERT INTO memories (id, content, layer, importance, created_at, metadata)
            VALUES (?, ?, 'episodic', ?, ?, ?)
        """, (
            f"cluster_{cluster.centroid_id}",
            summary,
            cluster.avg_importance,
            datetime.now().timestamp(),
            json.dumps({
                'type': 'cluster_summary',
                'member_count': len(cluster.member_ids),
                'member_ids': cluster.member_ids[:10]  # First 10
            })
        ))

        # Mark original memories as having a summary
        cursor.execute(f"""
            UPDATE memories 
            SET metadata = json_set(COALESCE(metadata, '{{}}'), '$.clustered', 1, '$.cluster_id', ?)
            WHERE id IN ({placeholders})
        """, [f"cluster_{cluster.centroid_id}"] + cluster.member_ids)

        conn.commit()
        conn.close()

        return summary

    def _update_importance_scores(self) -> int:
        """Update importance scores based on access patterns and age"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all unarchived memories
        cursor.execute("""
            SELECT id, importance, access_count, created_at, last_accessed
            FROM memories 
            WHERE archived = 0
        """)

        memories = cursor.fetchall()
        now = datetime.now().timestamp()
        updated = 0

        for id, importance, access_count, created_at, last_accessed in memories:
            # Calculate new score
            score = importance

            # Boost for access count (capped)
            access_boost = min(access_count * 0.02, 0.3)
            score += access_boost

            # Decay based on age
            age_days = (now - created_at) / 86400
            if age_days > 30:
                decay = min(0.1 * (age_days / 30 - 1), 0.3)
                score -= decay

            # Boost if recently accessed
            if last_accessed:
                hours_since_access = (now - last_accessed) / 3600
                if hours_since_access < 24:
                    score += 0.1
                elif hours_since_access < 168:  # 1 week
                    score += 0.05

            # Clamp score
            score = max(0.1, min(1.0, score))

            # Update if changed significantly
            if abs(score - importance) > 0.05:
                cursor.execute("""
                    UPDATE memories SET importance = ? WHERE id = ?
                """, (score, id))
                updated += 1

        conn.commit()
        conn.close()

        if updated > 0:
            logger.info(f"Updated {updated} importance scores")

        return updated

    def _promote_to_semantic(self, min_importance: float = 0.8, min_access: int = 5) -> int:
        """Promote high-value episodic memories to semantic layer"""
        from layers.entity_extractor import EntityExtractor

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Find candidates for promotion
        cursor.execute("""
            SELECT id, content, metadata
            FROM memories 
            WHERE archived = 0
            AND importance >= ?
            AND access_count >= ?
            AND (metadata IS NULL OR metadata NOT LIKE '%promoted%')
            LIMIT 50
        """, (min_importance, min_access))

        candidates = cursor.fetchall()
        promoted = 0

        extractor = EntityExtractor()

        for id, content, metadata in candidates:
            # Extract entities for semantic storage
            entities = extractor.extract_entities(content)
            relationships = extractor.extract_relationships(content, entities)

            if entities or relationships:
                # Store in semantic layer (Neo4j)
                try:
                    self._store_in_semantic(content, entities, relationships)

                    # Mark as promoted
                    meta = json.loads(metadata) if metadata else {}
                    meta['promoted'] = True
                    meta['promoted_at'] = datetime.now().isoformat()

                    cursor.execute("""
                        UPDATE memories SET metadata = ? WHERE id = ?
                    """, (json.dumps(meta), id))

                    promoted += 1
                except Exception as e:
                    logger.error(f"Failed to promote memory {id}: {e}")

        conn.commit()
        conn.close()

        if promoted > 0:
            logger.info(f"Promoted {promoted} memories to semantic layer")

        return promoted

    def _store_in_semantic(self, content: str, entities: List, relationships: List):
        """Store memory with entities in Neo4j"""
        from neo4j import GraphDatabase
        import json

        try:
            driver = GraphDatabase.driver("bolt://localhost:7687")

            with driver.session() as session:
                # Create memory node
                memory_id = f"auto_{datetime.now().timestamp()}"
                session.run("""
                    CREATE (m:Memory {id: $id, content: $content, created: $created})
                """, {
                    'id': memory_id,
                    'content': content[:500],
                    'created': datetime.now().timestamp()
                })

                # Create entities and relationships
                for entity in entities:
                    session.run("""
                        MERGE (e:Entity {canonical: $canonical})
                        SET e.name = $name, e.type = $type
                        WITH e
                        MATCH (m:Memory {id: $memory_id})
                        MERGE (m)-[:MENTIONS]->(e)
                    """, {
                        'canonical': entity.canonical,
                        'name': entity.name,
                        'type': entity.type,
                        'memory_id': memory_id
                    })

                for rel in relationships:
                    session.run("""
                        MERGE (s:Entity {canonical: $source})
                        MERGE (t:Entity {canonical: $target})
                        MERGE (s)-[r:RELATES {type: $type}]->(t)
                        SET r.evidence = $evidence
                    """, {
                        'source': rel.source,
                        'target': rel.target,
                        'type': rel.type,
                        'evidence': rel.evidence[:200] if rel.evidence else ''
                    })

            driver.close()
        except Exception as e:
            logger.error(f"Neo4j storage failed: {e}")
            raise


if __name__ == "__main__":
    # Test
    print("Running smart consolidation...")

    consolidator = SmartConsolidator()
    results = consolidator.run_consolidation()

    print("\nConsolidation results:")
    for key, value in results.items():
        print(f"  {key}: {value}")
