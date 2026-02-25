#!/usr/bin/env python3
"""
Setup script for OpenClaw 4-Layer Memory System
Installs dependencies, initializes databases, configures services
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run shell command with error handling"""
    if description:
        print(f"\n🔄 {description}")
    print(f"   $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ⚠ Error: {result.stderr}")
        return False
    print(f"   ✓ Success")
    return True


def check_service(service_name, check_cmd):
    """Check if a service is running"""
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    return result.returncode == 0


def setup_redis():
    """Setup Redis for working memory"""
    print("\n📦 Setting up Redis (Working Memory Layer)")
    
    # Check if Redis is installed
    if not run_command("which redis-server", "Checking Redis installation"):
        print("   Installing Redis...")
        run_command("apt-get update && apt-get install -y redis-server", "Installing Redis")
    
    # Check if Redis is running
    if not check_service("redis", "redis-cli ping"):
        run_command("systemctl start redis-server", "Starting Redis")
        run_command("systemctl enable redis-server", "Enabling Redis on boot")
    else:
        print("   ✓ Redis already running")
    
    # Test connection
    run_command("redis-cli ping", "Testing Redis connection")


def setup_neo4j():
    """Setup Neo4j for semantic memory"""
    print("\n📦 Setting up Neo4j (Semantic Memory Layer)")
    
    # Check if Neo4j is installed
    if not run_command("which neo4j", "Checking Neo4j installation"):
        print("   Installing Neo4j...")
        # Add Neo4j repository
        run_command("wget -O - https://debian.neo4j.com/neotechnology.gpg.key | apt-key add -")
        run_command('echo "deb https://debian.neo4j.com stable 4.0 main" | tee /etc/apt/sources.list.d/neo4j.list')
        run_command("apt-get update && apt-get install -y neo4j", "Installing Neo4j")
    
    # Check if Neo4j is running
    if not check_service("neo4j", "curl -s http://localhost:7474"):
        run_command("systemctl start neo4j", "Starting Neo4j")
        run_command("systemctl enable neo4j", "Enabling Neo4j on boot")
    else:
        print("   ✓ Neo4j already running")


def install_python_deps():
    """Install Python dependencies"""
    print("\n📦 Installing Python dependencies")
    
    deps = [
        "redis",
        "neo4j-python-driver",
        "numpy",
        "transformers",
        "torch",
        "spacy",
        "sentence-transformers"
    ]
    
    for dep in deps:
        run_command(f"pip3 install {dep}", f"Installing {dep}")


def init_databases():
    """Initialize SQLite databases"""
    print("\n🗄️ Initializing SQLite databases")
    
    base_path = "/root/.openclaw/memory-system"
    os.makedirs(base_path, exist_ok=True)
    
    # Episodic and Procedural databases will be created on first use
    print("   ✓ Database directory ready")


def setup_cron_jobs():
    """Setup cron jobs for memory maintenance"""
    print("\n⏰ Setting up cron jobs")
    
    cron_entries = """
# Memory System Maintenance
# Consolidate memories nightly at 2 AM
0 2 * * * cd /root/.openclaw/memory-system && python3 -c "import asyncio; from integration import FileMemoryBridge; b = FileMemoryBridge('ava'); asyncio.run(b.initialize()); asyncio.run(b.promote_important_memories())" >> /var/log/memory-consolidation.log 2>&1

# Memory health check every hour
0 * * * * cd /root/.openclaw/memory-system && python3 -c "from layers.episodic import EpisodicMemoryLayer; e = EpisodicMemoryLayer(); e.connect(); print(e.get_stats())" >> /var/log/memory-health.log 2>&1
"""
    
    # Add to crontab
    with open("/tmp/memory_cron.txt", "w") as f:
        f.write(cron_entries)
    
    run_command("crontab /tmp/memory_cron.txt", "Installing memory cron jobs")


def create_systemd_services():
    """Create systemd services for memory layers"""
    print("\n🔧 Creating systemd services")
    
    # Memory manager service
    service_content = """[Unit]
Description=OpenClaw NeuroMemory Manager
After=redis-server.service neo4j.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/memory-system
ExecStart=/usr/bin/python3 /root/.openclaw/memory-system/integration.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    with open("/etc/systemd/system/neuromemory.service", "w") as f:
        f.write(service_content)
    
    run_command("systemctl daemon-reload", "Reloading systemd")
    run_command("systemctl enable neuromemory.service", "Enabling memory service")


def verify_installation():
    """Verify everything is working"""
    print("\n✅ Verifying installation")
    
    checks = [
        ("Redis", "redis-cli ping"),
        ("Neo4j", "curl -s http://localhost:7474"),
        ("Python deps", "python3 -c 'import redis, neo4j, numpy'"),
        ("Memory system", "python3 -c 'import sys; sys.path.insert(0, \"/root/.openclaw/memory-system\"); from core.manager import NeuroMemoryManager'"),
    ]
    
    all_passed = True
    for name, cmd in checks:
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode == 0:
            print(f"   ✓ {name}")
        else:
            print(f"   ✗ {name} - FAILED")
            all_passed = False
    
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Setup OpenClaw 4-Layer Memory System")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--skip-services", action="store_true", help="Skip service setup")
    parser.add_argument("--verify-only", action="store_true", help="Only verify installation")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OPENCLAW 4-LAYER MEMORY SYSTEM SETUP")
    print("=" * 60)
    
    if args.verify_only:
        verify_installation()
        return
    
    if not args.skip_deps:
        setup_redis()
        setup_neo4j()
        install_python_deps()
    
    init_databases()
    
    if not args.skip_services:
        setup_cron_jobs()
        create_systemd_services()
    
    print("\n" + "=" * 60)
    if verify_installation():
        print("✅ Setup complete! Memory system ready.")
        print("\nNext steps:")
        print("  1. Start services: systemctl start neuromemory")
        print("  2. Test: python3 /root/.openclaw/memory-system/integration.py")
        print("  3. Check stats: python3 /root/.openclaw/memory-system/monitor.py")
    else:
        print("⚠️  Setup incomplete. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
