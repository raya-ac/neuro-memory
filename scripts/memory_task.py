#!/usr/bin/env python3
"""
Memory Task System - Store memories when tasks complete or are abandoned

Usage:
    python3 memory_task.py <agent> start <task_name> <description>
    python3 memory_task.py <agent> update <task_name> <progress> <details>
    python3 memory_task.py <agent> complete <task_name> <summary>
    python3 memory_task.py <agent> abandon <task_name> <reason>
    python3 memory_task.py <agent> list
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Add paths
sys.path.insert(0, '/root/.openclaw/memory-system')

from core.manager import NeuroMemoryManager
from core.base import MemoryLayer


class TaskMemory:
    """Manages task-based memory storage"""
    
    def __init__(self, agent: str):
        self.agent = agent
        self.manager: Optional[NeuroMemoryManager] = None
        self.current_task: Optional[Dict] = None
    
    async def connect(self):
        """Connect to memory system"""
        self.manager = NeuroMemoryManager()
        await self.manager.connect()
    
    async def disconnect(self):
        """Disconnect from memory system"""
        if self.manager:
            await self.manager.disconnect()
    
    async def start_task(self, task_name: str, description: str, 
                         metadata: Dict = None) -> str:
        """
        Log task start - stores in episodic memory
        
        Returns task_id for tracking
        """
        task_id = f"{self.agent}_{task_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        content = f"""# Task Started: {task_name}

**Agent:** {self.agent}
**Started:** {datetime.utcnow().isoformat()}
**Description:** {description}
**Task ID:** {task_id}

## Status
🟡 In Progress
"""
        
        await self.manager.remember(
            content=content,
            layer=MemoryLayer.EPISODIC,
            importance=0.6,
            metadata={
                "type": "task_start",
                "task_name": task_name,
                "task_id": task_id,
                "agent": self.agent,
                **(metadata or {})
            }
        )
        
        self.current_task = {
            "id": task_id,
            "name": task_name,
            "description": description,
            "started": datetime.utcnow().isoformat()
        }
        
        print(f"✅ Task started: {task_name}")
        print(f"   Task ID: {task_id}")
        return task_id
    
    async def update_task(self, task_name: str, progress: str, 
                          details: str = "") -> bool:
        """
        Log task progress update
        """
        content = f"""# Task Update: {task_name}

**Agent:** {self.agent}
**Time:** {datetime.utcnow().isoformat()}
**Progress:** {progress}

{f'**Details:** {details}' if details else ''}
"""
        
        await self.manager.remember(
            content=content,
            layer=MemoryLayer.WORKING,
            importance=0.4,
            metadata={
                "type": "task_update",
                "task_name": task_name,
                "agent": self.agent,
                "progress": progress
            }
        )
        
        print(f"📝 Task updated: {task_name} - {progress}")
        return True
    
    async def complete_task(self, task_name: str, summary: str,
                           outcome: str = "success", 
                           files_changed: list = None,
                           next_steps: list = None) -> bool:
        """
        Log task completion - stores comprehensive memory
        
        This is called when a task is successfully completed.
        """
        files_section = ""
        if files_changed:
            files_section = "\n## Files Changed\n" + "\n".join(f"- {f}" for f in files_changed)
        
        next_section = ""
        if next_steps:
            next_section = "\n## Next Steps\n" + "\n".join(f"- {s}" for s in next_steps)
        
        content = f"""# Task Completed: {task_name}

**Agent:** {self.agent}
**Completed:** {datetime.utcnow().isoformat()}
**Outcome:** ✅ {outcome.upper()}

## Summary
{summary}
{files_section}
{next_section}

---
*Stored in long-term memory for future reference*
"""
        
        # Store in episodic (event memory)
        await self.manager.remember(
            content=content,
            layer=MemoryLayer.EPISODIC,
            importance=0.8,  # Higher importance for completed tasks
            metadata={
                "type": "task_complete",
                "task_name": task_name,
                "agent": self.agent,
                "outcome": outcome,
                "files": files_changed,
                "next_steps": next_steps
            }
        )
        
        # Also store key learnings in semantic (knowledge)
        if outcome == "success":
            learning = f"When working on {task_name}: {summary[:200]}"
            await self.manager.remember(
                content=learning,
                layer=MemoryLayer.SEMANTIC,
                importance=0.7,
                metadata={
                    "type": "task_learning",
                    "task_name": task_name,
                    "agent": self.agent
                }
            )
        
        self.current_task = None
        print(f"✅ Task completed: {task_name}")
        print(f"   Outcome: {outcome}")
        return True
    
    async def abandon_task(self, task_name: str, reason: str,
                          partial_work: str = "",
                          resume_info: str = "") -> bool:
        """
        Log task abandonment - stores state for potential resume
        
        This is called when user wants to stop or task is paused.
        """
        partial_section = ""
        if partial_work:
            partial_section = f"\n## Work Completed So Far\n{partial_work}"
        
        resume_section = ""
        if resume_info:
            resume_section = f"\n## How to Resume\n{resume_info}"
        
        content = f"""# Task Paused: {task_name}

**Agent:** {self.agent}
**Paused:** {datetime.utcnow().isoformat()}
**Reason:** {reason}

## Status
🟡 PAUSED - Can be resumed
{partial_section}
{resume_section}

---
*Memory saved for future continuation*
"""
        
        # Store in episodic with high importance (we want to remember this)
        await self.manager.remember(
            content=content,
            layer=MemoryLayer.EPISODIC,
            importance=0.75,
            metadata={
                "type": "task_paused",
                "task_name": task_name,
                "agent": self.agent,
                "reason": reason,
                "can_resume": True
            }
        )
        
        # Store resume info in working memory for quick access
        if resume_info:
            await self.manager.remember(
                content=f"RESUME: {task_name}\n{resume_info}",
                layer=MemoryLayer.WORKING,
                importance=0.8,
                metadata={
                    "type": "resume_info",
                    "task_name": task_name
                }
            )
        
        self.current_task = None
        print(f"⏸️ Task paused: {task_name}")
        print(f"   Reason: {reason}")
        print(f"   Memory saved for future resume")
        return True
    
    async def fail_task(self, task_name: str, error: str,
                       attempted_solutions: list = None) -> bool:
        """
        Log task failure - stores error for learning
        """
        solutions_section = ""
        if attempted_solutions:
            solutions_section = "\n## Attempted Solutions\n" + "\n".join(
                f"- {s}" for s in attempted_solutions
            )
        
        content = f"""# Task Failed: {task_name}

**Agent:** {self.agent}
**Failed:** {datetime.utcnow().isoformat()}

## Error
{error}
{solutions_section}

---
*Stored for error pattern learning*
"""
        
        # Store in episodic
        await self.manager.remember(
            content=content,
            layer=MemoryLayer.EPISODIC,
            importance=0.7,
            metadata={
                "type": "task_failed",
                "task_name": task_name,
                "agent": self.agent,
                "error": error
            }
        )
        
        # Store pattern in procedural (how NOT to do things)
        await self.manager.remember(
            content=f"Error pattern in {task_name}: {error[:150]}",
            layer=MemoryLayer.PROCEDURAL,
            importance=0.8,
            metadata={
                "type": "error_pattern",
                "task_name": task_name
            }
        )
        
        self.current_task = None
        print(f"❌ Task failed: {task_name}")
        print(f"   Error: {error[:100]}...")
        return True
    
    async def list_recent_tasks(self, hours: int = 24) -> list:
        """List recent tasks from memory"""
        memories = await self.manager.recall_recent(hours=hours)
        
        tasks = []
        for m in memories:
            meta = m.metadata or {}
            if meta.get("type", "").startswith("task_"):
                tasks.append({
                    "name": meta.get("task_name", "Unknown"),
                    "type": meta.get("type", ""),
                    "time": m.created_at,
                    "importance": m.importance
                })
        
        return tasks


async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nExamples:")
        print("  python3 memory_task.py eva start 'fix-bug' 'Fixing login bug'")
        print("  python3 memory_task.py eva update 'fix-bug' '50%' 'Found root cause'")
        print("  python3 memory_task.py eva complete 'fix-bug' 'Fixed by updating config'")
        print("  python3 memory_task.py eva abandon 'fix-bug' 'User requested pause'")
        print("  python3 memory_task.py eva list")
        sys.exit(1)
    
    agent = sys.argv[1]
    command = sys.argv[2]
    
    tm = TaskMemory(agent)
    await tm.connect()
    
    try:
        if command == "start":
            if len(sys.argv) < 5:
                print("Usage: memory_task.py <agent> start <task_name> <description>")
                sys.exit(1)
            task_name = sys.argv[3]
            description = sys.argv[4]
            await tm.start_task(task_name, description)
        
        elif command == "update":
            if len(sys.argv) < 5:
                print("Usage: memory_task.py <agent> update <task_name> <progress> [details]")
                sys.exit(1)
            task_name = sys.argv[3]
            progress = sys.argv[4]
            details = sys.argv[5] if len(sys.argv) > 5 else ""
            await tm.update_task(task_name, progress, details)
        
        elif command == "complete":
            if len(sys.argv) < 5:
                print("Usage: memory_task.py <agent> complete <task_name> <summary>")
                sys.exit(1)
            task_name = sys.argv[3]
            summary = sys.argv[4]
            await tm.complete_task(task_name, summary)
        
        elif command == "abandon":
            if len(sys.argv) < 5:
                print("Usage: memory_task.py <agent> abandon <task_name> <reason>")
                sys.exit(1)
            task_name = sys.argv[3]
            reason = sys.argv[4]
            await tm.abandon_task(task_name, reason)
        
        elif command == "fail":
            if len(sys.argv) < 5:
                print("Usage: memory_task.py <agent> fail <task_name> <error>")
                sys.exit(1)
            task_name = sys.argv[3]
            error = sys.argv[4]
            await tm.fail_task(task_name, error)
        
        elif command == "list":
            tasks = await tm.list_recent_tasks()
            if tasks:
                print(f"📋 Recent tasks for {agent}:")
                for t in tasks:
                    print(f"   {t['type']}: {t['name']} ({t['time']})")
            else:
                print(f"No recent tasks for {agent}")
        
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
    
    finally:
        await tm.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
