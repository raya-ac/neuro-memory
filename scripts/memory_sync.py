#!/usr/bin/env python3
"""
Memory Sync Script
- Syncs mind/ and memory/ files to the 4-layer system
- Can be run manually or via cron
- Idempotent - safe to run multiple times

Standalone - does not depend on integration.py
"""

import sys
import os
import json
import hashlib
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
logger = logging.getLogger("memory-sync")

# Config
MEMORY_SYSTEM_DIR = Path("/root/.openclaw/memory-system")
CONFIG_FILE = MEMORY_SYSTEM_DIR / "config.json"
EPISODIC_DB = MEMORY_SYSTEM_DIR / "episodic.db"
PROCEDURAL_DB = MEMORY_SYSTEM_DIR / "procedural.db"

# Agent workspaces
AGENTS = {
    "ava": "/root/.openclaw/workspace-ava",
    "eva": "/root/.openclaw/workspace-eva",
    "main": "/root/.openclaw/workspace"  # Main workspace too
}


def load_config():
    """Load config from JSON file"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def generate_memory_id(filepath: str, content: str) -> str:
    """Generate unique ID for a file"""
    hash_input = f"{filepath}:{content[:100]}".encode()
    return hashlib.md5(hash_input).hexdigest()[:12]


def sync_to_episodic(agent: str, filepath: str, content: str, importance: float = 0.5):
    """Sync a file to episodic memory (SQLite)"""
    conn = sqlite3.connect(str(EPISODIC_DB))
    cursor = conn.cursor()
    
    memory_id = f"file:{generate_memory_id(filepath, content)}"
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO memories 
            (id, content, layer, importance, created_at, last_accessed, metadata)
            VALUES (?, ?, 'episodic', ?, ?, ?, ?)
        """, (
            memory_id,
            content[:8000],  # Limit size
            importance,
            os.path.getmtime(filepath),
            datetime.now().timestamp(),
            json.dumps({"source_file": filepath, "agent": agent})
        ))
        conn.commit()
        return memory_id
    except Exception as e:
        logger.error(f"Failed to sync {filepath}: {e}")
        return None
    finally:
        conn.close()


def sync_to_semantic(agent: str, filepath: str, content: str, entities: list = None):
    """Sync a file to semantic memory (Neo4j)"""
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
        
        memory_id = f"file:{generate_memory_id(filepath, content)}"
        
        with driver.session() as session:
            # Create/update memory node
            session.run("""
                MERGE (m:Memory {id: $id})
                SET m.content = $content,
                    m.source_file = $filepath,
                    m.agent = $agent,
                    m.last_synced = $now
            """, {
                'id': memory_id,
                'content': content[:4000],
                'filepath': filepath,
                'agent': agent,
                'now': datetime.now().timestamp()
            })
            
            # Create entities if provided
            if entities:
                for entity in entities:
                    session.run("""
                        MERGE (e:Entity {canonical: $canonical})
                        SET e.name = $name, e.type = $type
                        WITH e
                        MATCH (m:Memory {id: $memory_id})
                        MERGE (m)-[:MENTIONS]->(e)
                    """, {
                        'canonical': entity.get('name', '').lower().replace(' ', '_'),
                        'name': entity.get('name', ''),
                        'type': entity.get('type', 'concept'),
                        'memory_id': memory_id
                    })
        
        driver.close()
        return memory_id
    except Exception as e:
        logger.error(f"Failed to sync to Neo4j {filepath}: {e}")
        return None


def get_importance_for_file(filepath: str) -> float:
    """Calculate importance based on file type"""
    if 'SOUL.md' in filepath or 'AGENTS.md' in filepath:
        return 1.0
    elif 'DECISIONS.md' in filepath:
        return 0.9
    elif 'ERRORS.md' in filepath:
        return 0.8
    elif 'PROJECTS.md' in filepath or 'GOALS.md' in filepath:
        return 0.85
    elif 'PROFILE.md' in filepath:
        return 0.8
    elif 'MEMORY.md' in filepath:
        return 0.75
    elif 'LOOPS.md' in filepath:
        return 0.7
    elif filepath.endswith('/memory/'):
        return 0.6
    else:
        return 0.5


def sync_agent(agent: str, workspace: str):
    """Sync all files for an agent"""
    logger.info(f"\nSyncing {agent.upper()}...")
    
    mind_dir = Path(workspace) / "mind"
    memory_dir = Path(workspace) / "memory"
    
    stats = {"episodic": 0, "semantic": 0, "errors": 0}
    
    # Sync all mind/ files recursively (includes logs/, ROADMAP/, CONTEXT/, etc.)
    if mind_dir.exists():
        for md_file in mind_dir.rglob("*.md"):
            try:
                content = md_file.read_text()
                importance = get_importance_for_file(str(md_file))
                
                # Sync to episodic
                if sync_to_episodic(agent, str(md_file), content, importance):
                    stats['episodic'] += 1
                
                # Sync important files to semantic too
                if importance >= 0.8:
                    if sync_to_semantic(agent, str(md_file), content):
                        stats['semantic'] += 1
                        
            except Exception as e:
                logger.error(f"Error processing {md_file}: {e}")
                stats['errors'] += 1
    
    # Sync memory/ files (daily logs and other memory files)
    if memory_dir.exists():
        for md_file in memory_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                
                # Daily logs go to episodic only
                if sync_to_episodic(agent, str(md_file), content, 0.6):
                    stats['episodic'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing {md_file}: {e}")
                stats['errors'] += 1
    
    logger.info(f"  Episodic: {stats['episodic']}")
    logger.info(f"  Semantic: {stats['semantic']}")
    if stats['errors']:
        logger.warning(f"  Errors: {stats['errors']}")
    
    return stats


def main():
    """Sync all agents"""
    logger.info("=" * 50)
    logger.info("MEMORY SYNC START")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    total_stats = {"episodic": 0, "semantic": 0, "errors": 0}
    
    for agent, workspace in AGENTS.items():
        if Path(workspace).exists():
            stats = sync_agent(agent, workspace)
            for key in total_stats:
                total_stats[key] += stats[key]
        else:
            logger.warning(f"Workspace not found: {workspace}")
    
    logger.info("\n" + "=" * 50)
    logger.info("MEMORY SYNC COMPLETE")
    logger.info(f"Total - Episodic: {total_stats['episodic']}, Semantic: {total_stats['semantic']}, Errors: {total_stats['errors']}")
    logger.info("=" * 50)
    
    return 0 if total_stats['errors'] == 0 else 1


if __name__ == "__main__":
    exit(main())
