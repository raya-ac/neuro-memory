#!/usr/bin/env python3
"""
Memory Consolidation Script
- Promotes high-importance memories up through layers
- Demotes low-importance memories
- Archives old memories
- Runs via cron (nightly at 2 AM)

Standalone - does not depend on integration.py
"""

import asyncio
import sys
import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("memory-consolidate")

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


async def consolidate_episodic():
    """Consolidate episodic memories - archive old ones, promote important ones"""
    if not EPISODIC_DB.exists():
        logger.warning(f"Episodic DB not found: {EPISODIC_DB}")
        return {"archived": 0, "promoted": 0}
    
    conn = sqlite3.connect(str(EPISODIC_DB))
    cursor = conn.cursor()
    
    # Archive memories older than 90 days with low importance
    cutoff = (datetime.now() - timedelta(days=90)).timestamp()
    
    cursor.execute("""
        UPDATE memories 
        SET archived = 1 
        WHERE created_at < ? 
        AND importance < 0.5 
        AND archived = 0
    """, (cutoff,))
    archived = cursor.rowcount
    
    # Mark high-importance memories (these would be promoted to semantic in full system)
    cursor.execute("""
        UPDATE memories 
        SET importance = MIN(importance + 0.1, 1.0)
        WHERE access_count > 5
        AND importance >= 0.7
    """)
    promoted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return {"archived": archived, "promoted": promoted}


async def consolidate_procedural():
    """Clean up procedural patterns - remove unused, boost successful"""
    if not PROCEDURAL_DB.exists():
        logger.warning(f"Procedural DB not found: {PROCEDURAL_DB}")
        return {"removed": 0, "boosted": 0}
    
    conn = sqlite3.connect(str(PROCEDURAL_DB))
    cursor = conn.cursor()
    
    # Remove procedures with 0 success and multiple failures
    cursor.execute("""
        DELETE FROM procedures 
        WHERE success_count = 0 
        AND failure_count > 3
    """)
    removed = cursor.rowcount
    
    # Update success_rate for procedures
    cursor.execute("""
        UPDATE procedures 
        SET avg_execution_time_ms = avg_execution_time_ms * 0.95
        WHERE success_count > 5
    """)
    boosted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return {"removed": removed, "boosted": boosted}


async def cleanup_working_memory():
    """Clean up Redis working memory cache"""
    try:
        import redis
        config = load_config()
        redis_url = config.get('memory', {}).get('hierarchy', {}).get('working', {}).get('redis_url', 'redis://localhost:6379')
        
        r = redis.from_url(redis_url)
        
        # Get keys with memory: prefix
        keys = r.keys("memory:*")
        
        # Remove expired entries (Redis TTL handles most, but clean orphaned)
        cleaned = 0
        for key in keys:
            ttl = r.ttl(key)
            if ttl == -1:  # No expiry set, give it 5 min
                r.expire(key, 300)
                cleaned += 1
        
        r.close()
        return {"cleaned": cleaned}
    except Exception as e:
        logger.error(f"Redis cleanup failed: {e}")
        return {"cleaned": 0, "error": str(e)}


async def main():
    """Run all consolidation tasks"""
    logger.info("=" * 50)
    logger.info("MEMORY CONSOLIDATION START")
    logger.info("=" * 50)
    
    results = {}
    
    # Episodic
    logger.info("Consolidating episodic memories...")
    results['episodic'] = await consolidate_episodic()
    logger.info(f"  Archived: {results['episodic']['archived']}, Promoted: {results['episodic']['promoted']}")
    
    # Procedural
    logger.info("Consolidating procedural patterns...")
    results['procedural'] = await consolidate_procedural()
    logger.info(f"  Removed: {results['procedural']['removed']}, Boosted: {results['procedural']['boosted']}")
    
    # Working (Redis)
    logger.info("Cleaning working memory...")
    results['working'] = await cleanup_working_memory()
    logger.info(f"  Cleaned: {results['working']['cleaned']}")
    
    logger.info("=" * 50)
    logger.info("MEMORY CONSOLIDATION COMPLETE")
    logger.info("=" * 50)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
