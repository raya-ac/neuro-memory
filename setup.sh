#!/bin/bash
# Quick setup script for NeuroMemory System

set -e

echo "========================================"
echo "NeuroMemory System - Quick Setup"
echo "========================================"

# Check Python version
echo ""
echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "      Found: Python $PYTHON_VERSION"

# Check Redis
echo ""
echo "[2/5] Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "      ✓ Redis is running"
else
    echo "      ✗ Redis not running. Install with:"
    echo "        apt install redis-server && systemctl start redis-server"
    exit 1
fi

# Check Neo4j
echo ""
echo "[3/5] Checking Neo4j..."
if curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo "      ✓ Neo4j is running"
else
    echo "      ✗ Neo4j not running. Install with:"
    echo "        apt install neo4j && systemctl start neo4j"
    echo ""
    echo "      To disable auth (recommended for localhost):"
    echo "        sed -i 's/dbms.security.auth_enabled=true/dbms.security.auth_enabled=false/' /etc/neo4j/neo4j.conf"
    echo "        systemctl restart neo4j"
    exit 1
fi

# Install Python dependencies
echo ""
echo "[4/5] Installing Python dependencies..."
pip install neo4j redis 2>/dev/null || pip3 install neo4j redis
echo "      ✓ Dependencies installed"

# Initialize databases
echo ""
echo "[5/5] Initializing databases..."
python3 << 'PYEOF'
import sqlite3
from pathlib import Path

# Create episodic DB
episodic_db = Path("episodic.db")
if not episodic_db.exists():
    conn = sqlite3.connect(str(episodic_db))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            layer TEXT DEFAULT 'episodic',
            importance REAL DEFAULT 0.5,
            created_at REAL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)
    c.execute("CREATE INDEX idx_created ON memories(created_at)")
    c.execute("CREATE INDEX idx_importance ON memories(importance)")
    conn.commit()
    conn.close()
    print("      Created episodic.db")

# Create procedural DB
procedural_db = Path("procedural.db")
if not procedural_db.exists():
    conn = sqlite3.connect(str(procedural_db))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE procedures (
            id TEXT PRIMARY KEY,
            pattern TEXT NOT NULL,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            last_success REAL,
            last_failure REAL,
            created_at REAL,
            updated_at REAL
        )
    """)
    conn.commit()
    conn.close()
    print("      Created procedural.db")

print("      ✓ Databases initialized")
PYEOF

echo ""
echo "========================================"
echo "✓ Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit config.json with your settings"
echo "  2. Add your agent workspaces to config.json"
echo "  3. Run: python3 -c 'from memory_integration import Memory; import asyncio; asyncio.run(Memory.initialize())'"
echo ""
echo "To set up cron jobs:"
echo "  ./scripts/memory_health.py       # Test health"
echo "  ./scripts/memory_sync.py         # Sync files"
echo "  crontab -e                       # Add scheduled jobs"
echo ""
