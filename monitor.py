#!/usr/bin/env python3
"""
Memory System Monitor - Real-time dashboard for 4-layer cognitive memory
"""

import sys
import time
import json
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/memory-system')

from core.manager import NeuroMemoryManager


class MemoryMonitor:
    """Real-time monitoring dashboard for memory system"""
    
    def __init__(self):
        self.manager = NeuroMemoryManager()
    
    async def connect(self):
        await self.manager.connect()
    
    def display_dashboard(self):
        """Display real-time memory stats"""
        stats = self.manager.get_all_stats()
        
        print("\033[2J\033[H")  # Clear screen
        print("=" * 70)
        print(f"🧠 NEUROMEMORY DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Layer statistics
        layers = [
            ('🔥 Working', stats.get('working', {})),
            ('📚 Episodic', stats.get('episodic', {})),
            ('🕸️ Semantic', stats.get('semantic', {})),
            ('⚙️ Procedural', stats.get('procedural', {})),
        ]
        
        for name, layer_stats in layers:
            print(f"\n{name} Memory")
            print("-" * 40)
            if layer_stats:
                for key, value in layer_stats.items():
                    if isinstance(value, float):
                        print(f"  {key:20}: {value:.3f}")
                    else:
                        print(f"  {key:20}: {value}")
            else:
                print("  (No data available)")
        
        # Overall performance
        print("\n📊 Overall Performance")
        print("-" * 40)
        total_queries = sum(s.get('queries', 0) for s in stats.values())
        total_hits = sum(s.get('hits', 0) for s in stats.values())
        avg_latency = sum(s.get('avg_latency_ms', 0) for s in stats.values()) / len(stats) if stats else 0
        
        print(f"  Total queries:        {total_queries}")
        print(f"  Cache hits:           {total_hits}")
        print(f"  Hit rate:             {(total_hits/total_queries*100) if total_queries else 0:.1f}%")
        print(f"  Avg latency:          {avg_latency:.2f}ms")
        
        print("\n" + "=" * 70)
        print("Press Ctrl+C to exit | Refreshing every 5 seconds")
    
    async def run(self, refresh_interval: int = 5):
        """Run monitoring loop"""
        await self.connect()
        
        try:
            while True:
                self.display_dashboard()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\n✓ Monitoring stopped")
        finally:
            await self.manager.disconnect()


if __name__ == "__main__":
    import asyncio
    monitor = MemoryMonitor()
    asyncio.run(monitor.run())
