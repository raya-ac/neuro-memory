#!/usr/bin/env python3
"""
Memory Health Check Script
- Checks all 4 layers are operational
- Reports stats to log
- Can send alerts if layers are down
- Runs via cron (hourly)

Standalone - does not depend on integration.py
"""

import sys
import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("memory-health")

# Config
MEMORY_SYSTEM_DIR = Path("/root/.openclaw/memory-system")
CONFIG_FILE = MEMORY_SYSTEM_DIR / "config.json"
EPISODIC_DB = MEMORY_SYSTEM_DIR / "episodic.db"
PROCEDURAL_DB = MEMORY_SYSTEM_DIR / "procedural.db"


def load_config():
    """Load config from JSON file"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def check_working_memory():
    """Check Redis working memory layer"""
    try:
        import redis
        config = load_config()
        redis_url = config.get('memory', {}).get('hierarchy', {}).get('working', {}).get('redis_url', 'redis://localhost:6379')
        
        r = redis.from_url(redis_url)
        r.ping()
        
        info = r.info('memory')
        keys = len(r.keys("memory:*"))
        r.close()
        
        return {
            "status": "healthy",
            "keys": keys,
            "used_memory": info.get('used_memory_human', 'unknown')
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_episodic_memory():
    """Check SQLite episodic memory layer"""
    try:
        if not EPISODIC_DB.exists():
            return {"status": "unhealthy", "error": "Database file not found"}
        
        conn = sqlite3.connect(str(EPISODIC_DB))
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM memories WHERE archived = 0")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM memories WHERE archived = 1")
        archived = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(importance) FROM memories")
        avg_importance = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "status": "healthy",
            "total_memories": total,
            "archived": archived,
            "avg_importance": round(avg_importance, 3)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_semantic_memory():
    """Check Neo4j semantic memory layer"""
    try:
        from neo4j import GraphDatabase
        
        config = load_config()
        neo4j_config = config.get('memory', {}).get('hierarchy', {}).get('semantic', {})
        
        uri = neo4j_config.get('neo4j_url', 'bolt://localhost:7687')
        user = neo4j_config.get('neo4j_user')
        password = neo4j_config.get('neo4j_pass')
        
        # Connect with or without auth
        if user and password:
            driver = GraphDatabase.driver(uri, auth=(user, password))
        else:
            driver = GraphDatabase.driver(uri)
        
        with driver.session() as session:
            # Get counts
            result = session.run("MATCH (m:Memory) RETURN count(m) as count")
            memory_count = result.single()['count']
            
            result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            entity_count = result.single()['count']
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
        
        driver.close()
        
        return {
            "status": "healthy",
            "memories": memory_count,
            "entities": entity_count,
            "relationships": rel_count
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_procedural_memory():
    """Check SQLite procedural memory layer"""
    try:
        if not PROCEDURAL_DB.exists():
            return {"status": "unhealthy", "error": "Database file not found"}
        
        conn = sqlite3.connect(str(PROCEDURAL_DB))
        cursor = conn.cursor()
        
        # Check procedures table (actual table name)
        cursor.execute("SELECT COUNT(*) FROM procedures")
        total = cursor.fetchone()[0]
        
        # Calculate success rate from counts
        cursor.execute("SELECT SUM(success_count), SUM(failure_count) FROM procedures")
        row = cursor.fetchone()
        success_total = row[0] or 0
        failure_total = row[1] or 0
        if success_total + failure_total > 0:
            avg_success = success_total / (success_total + failure_total)
        else:
            avg_success = 0
        
        conn.close()
        
        return {
            "status": "healthy",
            "total_patterns": total,
            "avg_success_rate": round(avg_success, 3)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def main():
    """Run health checks on all layers"""
    logger.info("=" * 50)
    logger.info("MEMORY HEALTH CHECK")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "layers": {}
    }
    
    # Check each layer
    logger.info("\n[L1] Working Memory (Redis):")
    results['layers']['working'] = check_working_memory()
    status = results['layers']['working']['status']
    logger.info(f"    Status: {status.upper()}")
    if status == 'healthy':
        logger.info(f"    Keys: {results['layers']['working']['keys']}")
        logger.info(f"    Memory: {results['layers']['working']['used_memory']}")
    else:
        logger.error(f"    Error: {results['layers']['working'].get('error')}")
    
    logger.info("\n[L2] Episodic Memory (SQLite):")
    results['layers']['episodic'] = check_episodic_memory()
    status = results['layers']['episodic']['status']
    logger.info(f"    Status: {status.upper()}")
    if status == 'healthy':
        logger.info(f"    Total: {results['layers']['episodic']['total_memories']}")
        logger.info(f"    Archived: {results['layers']['episodic']['archived']}")
        logger.info(f"    Avg Importance: {results['layers']['episodic']['avg_importance']}")
    else:
        logger.error(f"    Error: {results['layers']['episodic'].get('error')}")
    
    logger.info("\n[L3] Semantic Memory (Neo4j):")
    results['layers']['semantic'] = check_semantic_memory()
    status = results['layers']['semantic']['status']
    logger.info(f"    Status: {status.upper()}")
    if status == 'healthy':
        logger.info(f"    Memories: {results['layers']['semantic']['memories']}")
        logger.info(f"    Entities: {results['layers']['semantic']['entities']}")
        logger.info(f"    Relationships: {results['layers']['semantic']['relationships']}")
    else:
        logger.error(f"    Error: {results['layers']['semantic'].get('error')}")
    
    logger.info("\n[L4] Procedural Memory (SQLite):")
    results['layers']['procedural'] = check_procedural_memory()
    status = results['layers']['procedural']['status']
    logger.info(f"    Status: {status.upper()}")
    if status == 'healthy':
        logger.info(f"    Patterns: {results['layers']['procedural']['total_patterns']}")
        logger.info(f"    Avg Success: {results['layers']['procedural']['avg_success_rate']}")
    else:
        logger.error(f"    Error: {results['layers']['procedural'].get('error')}")
    
    # Summary
    healthy_count = sum(1 for l in results['layers'].values() if l.get('status') == 'healthy')
    total_count = len(results['layers'])
    
    logger.info("\n" + "=" * 50)
    logger.info(f"SUMMARY: {healthy_count}/{total_count} layers healthy")
    logger.info("=" * 50)
    
    # Return non-zero if any layer unhealthy
    if healthy_count < total_count:
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
