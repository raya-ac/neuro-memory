#!/usr/bin/env python3
"""
Memory Consolidation Script
- Uses SmartConsolidator for intelligent consolidation
- Clusters similar memories
- Summarizes large clusters
- Updates importance scores
- Promotes high-value memories to semantic
- Runs via cron (nightly at 2 AM)
"""

import asyncio
import sys
import os
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


async def run_smart_consolidation():
    """Run the smart consolidator"""
    try:
        from core.consolidator import SmartConsolidator
        
        consolidator = SmartConsolidator()
        results = consolidator.run_consolidation()
        
        logger.info("Smart consolidation results:")
        for key, value in results.items():
            logger.info(f"  {key}: {value}")
        
        return results
    except ImportError:
        logger.warning("SmartConsolidator not available, using legacy consolidation")
        return await run_legacy_consolidation()
    except Exception as e:
        logger.error(f"Smart consolidation failed: {e}")
        return await run_legacy_consolidation()


async def run_legacy_consolidation():
    """Legacy consolidation if SmartConsolidator unavailable"""
    import sqlite3
    import json
    
    MEMORY_SYSTEM_DIR = Path("/root/.openclaw/memory-system")
    EPISODIC_DB = MEMORY_SYSTEM_DIR / "episodic.db"
    PROCEDURAL_DB = MEMORY_SYSTEM_DIR / "procedural.db"
    CONFIG_FILE = MEMORY_SYSTEM_DIR / "config.json"
    
    results = {}
    
    # Episodic consolidation
    if EPISODIC_DB.exists():
        conn = sqlite3.connect(str(EPISODIC_DB))
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=90)).timestamp()
        
        cursor.execute("""
            UPDATE memories 
            SET archived = 1 
            WHERE created_at < ? 
            AND importance < 0.5 
            AND archived = 0
        """, (cutoff,))
        results['archived'] = cursor.rowcount
        
        cursor.execute("""
            UPDATE memories 
            SET importance = MIN(importance + 0.1, 1.0)
            WHERE access_count > 5
            AND importance >= 0.7
        """)
        results['promoted'] = cursor.rowcount
        
        conn.commit()
        conn.close()
    
    # Procedural consolidation
    if PROCEDURAL_DB.exists():
        conn = sqlite3.connect(str(PROCEDURAL_DB))
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM procedures 
            WHERE success_count = 0 
            AND failure_count > 3
        """)
        results['removed'] = cursor.rowcount
        
        conn.commit()
        conn.close()
    
    # Working memory cleanup
    try:
        import redis
        
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
        
        redis_url = config.get('memory', {}).get('hierarchy', {}).get('working', {}).get('redis_url', 'redis://localhost:6379')
        r = redis.from_url(redis_url)
        
        keys = r.keys("memory:*")
        cleaned = 0
        for key in keys:
            ttl = r.ttl(key)
            if ttl == -1:
                r.expire(key, 300)
                cleaned += 1
        
        results['cleaned'] = cleaned
        r.close()
    except Exception as e:
        logger.warning(f"Redis cleanup failed: {e}")
        results['cleaned'] = 0
    
    return results


async def main():
    """Run all consolidation tasks"""
    logger.info("=" * 50)
    logger.info("MEMORY CONSOLIDATION START")
    logger.info("=" * 50)
    
    results = await run_smart_consolidation()
    
    logger.info("=" * 50)
    logger.info("MEMORY CONSOLIDATION COMPLETE")
    logger.info("=" * 50)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
