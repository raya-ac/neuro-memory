#!/usr/bin/env python3
"""
FileSystemBridge - Bridge between 4-layer memory and existing file-based system
Migrates and syncs data between the two systems
"""

import os
import re
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, '/root/.openclaw/memory-system')

from core.base import MemoryEntry, MemoryLayer
from core.manager import NeuroMemoryManager

import logging
logger = logging.getLogger("neuro-memory.bridge")


class FileSystemBridge:
    """
    Bridges the 4-layer cognitive memory with the existing file-based system:
    - mind/*.md files → Semantic layer
    - memory/*.md files → Episodic layer
    - Patterns → Procedural layer
    """
    
    def __init__(self, 
                 workspace_path: str = "/root/.openclaw/workspace-ava",
                 memory_manager: Optional[NeuroMemoryManager] = None):
        
        self.workspace = Path(workspace_path)
        self.mind_dir = self.workspace / "mind"
        self.memory_dir = self.workspace / "memory"
        
        self.manager = memory_manager or NeuroMemoryManager()
        self._entity_patterns = {
            'person': r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',
            'project': r'\b([A-Z][a-z]+[A-Z][a-z]*)\b',
            'technology': r'\b(Python|JavaScript|Go|Redis|Neo4j|Docker|Kubernetes)\b'
        }
    
    async def connect(self):
        """Initialize memory manager"""
        await self.manager.connect()
    
    async def disconnect(self):
        """Close connections"""
        await self.manager.disconnect()
    
    async def sync_mind_files(self):
        """
        Sync mind/ directory to semantic memory
        Extracts entities and relationships
        """
        if not self.mind_dir.exists():
            logger.warning(f"Mind directory not found: {self.mind_dir}")
            return
        
        synced = 0
        
        for md_file in self.mind_dir.glob("*.md"):
            if md_file.name == "SHARED.md":
                continue  # Skip shared file
            
            content = md_file.read_text()
            
            # Parse sections as separate memories
            sections = self._parse_markdown_sections(content)
            
            for section in sections:
                # Extract entities
                entities = self._extract_entities(section['content'])
                
                # Store in semantic layer
                memory_id = await self.manager.remember(
                    content=section['content'],
                    layer=MemoryLayer.SEMANTIC,
                    importance=section.get('importance', 0.5),
                    metadata={
                        'source_file': md_file.name,
                        'section_title': section.get('title', ''),
                        'file_mtime': md_file.stat().st_mtime
                    },
                    entities=entities
                )
                
                synced += 1
        
        logger.info(f"Synced {synced} sections from mind/ to semantic memory")
        return synced
    
    async def sync_memory_files(self):
        """
        Sync memory/ directory (daily logs) to episodic memory
        """
        if not self.memory_dir.exists():
            logger.warning(f"Memory directory not found: {self.memory_dir}")
            return
        
        synced = 0
        
        for md_file in sorted(self.memory_dir.glob("*.md")):
            content = md_file.read_text()
            
            # Parse as daily log
            date = self._parse_date_from_filename(md_file.name)
            
            # Split into entries (activity log sections)
            entries = self._parse_log_entries(content)
            
            for entry in entries:
                await self.manager.remember(
                    content=entry['content'],
                    layer=MemoryLayer.EPISODIC,
                    importance=entry.get('importance', 0.3),
                    metadata={
                        'source_file': md_file.name,
                        'date': date,
                        'entry_type': entry.get('type', 'log')
                    }
                )
                synced += 1
        
        logger.info(f"Synced {synced} entries from memory/ to episodic memory")
        return synced
    
    async def sync_patterns(self):
        """
        Extract patterns from decisions and errors to procedural memory
        """
        patterns_synced = 0
        
        # Read decisions
        decisions_file = self.mind_dir / "DECISIONS.md"
        if decisions_file.exists():
            content = decisions_file.read_text()
            decisions = self._parse_decisions(content)
            
            for decision in decisions:
                await self.manager.remember(
                    content=decision['content'],
                    layer=MemoryLayer.PROCEDURAL,
                    importance=decision.get('importance', 0.6),
                    metadata={
                        'type': 'decision',
                        'tags': decision.get('tags', [])
                    }
                )
                patterns_synced += 1
        
        # Read errors
        errors_file = self.mind_dir / "ERRORS.md"
        if errors_file.exists():
            content = errors_file.read_text()
            errors = self._parse_errors(content)
            
            for error in errors:
                await self.manager.remember(
                    content=error['content'],
                    layer=MemoryLayer.PROCEDURAL,
                    importance=0.7,  # Errors are important patterns
                    metadata={
                        'type': 'error',
                        'prevention_rule': error.get('prevention', '')
                    }
                )
                patterns_synced += 1
        
        logger.info(f"Synced {patterns_synced} patterns to procedural memory")
        return patterns_synced
    
    async def full_sync(self):
        """Run complete sync from file system to memory system"""
        results = {
            'semantic': await self.sync_mind_files(),
            'episodic': await self.sync_memory_files(),
            'procedural': await self.sync_patterns()
        }
        return results
    
    async def query_and_update_files(self, query: str) -> List[Dict]:
        """
        Query memory system and suggest file updates
        """
        results = await self.manager.recall(query, limit=10)
        
        # Group by source file
        by_file = {}
        for memory in results:
            source = memory.metadata.get('source_file', 'unknown')
            if source not in by_file:
                by_file[source] = []
            by_file[source].append({
                'id': memory.id,
                'content': memory.content[:200] + '...',
                'importance': memory.importance
            })
        
        return by_file
    
    # Parsing helpers
    
    def _parse_markdown_sections(self, content: str) -> List[Dict]:
        """Parse markdown into sections"""
        sections = []
        current_section = {'title': '', 'content': '', 'importance': 0.5}
        
        for line in content.split('\n'):
            if line.startswith('# '):
                if current_section['content']:
                    sections.append(current_section)
                current_section = {
                    'title': line[2:].strip(),
                    'content': line + '\n',
                    'importance': 0.7  # Top-level headers are important
                }
            elif line.startswith('## '):
                if current_section['content']:
                    sections.append(current_section)
                current_section = {
                    'title': line[3:].strip(),
                    'content': line + '\n',
                    'importance': 0.5
                }
            else:
                current_section['content'] += line + '\n'
        
        if current_section['content']:
            sections.append(current_section)
        
        return sections
    
    def _parse_log_entries(self, content: str) -> List[Dict]:
        """Parse daily log into entries"""
        entries = []
        current_entry = {'content': '', 'type': 'log', 'importance': 0.3}
        
        for line in content.split('\n'):
            # Match time-based entries like "### 04:40 UTC — Entry Title"
            if re.match(r'###\s+\d{2}:\d{2}', line):
                if current_entry['content']:
                    entries.append(current_entry)
                current_entry = {
                    'content': line + '\n',
                    'type': 'activity',
                    'importance': 0.4
                }
            else:
                current_entry['content'] += line + '\n'
        
        if current_entry['content']:
            entries.append(current_entry)
        
        return entries
    
    def _parse_decisions(self, content: str) -> List[Dict]:
        """Extract decisions from DECISIONS.md"""
        decisions = []
        
        # Match ### YYYY-MM-DD — Decision Title
        pattern = r'###\s+(\d{4}-\d{2}-\d{2})\s+—\s+(.+?)(?=###|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for date, body in matches:
            decisions.append({
                'date': date,
                'content': body.strip(),
                'importance': 0.6,
                'tags': self._extract_tags(body)
            })
        
        return decisions
    
    def _parse_errors(self, content: str) -> List[Dict]:
        """Extract errors from ERRORS.md"""
        errors = []
        
        pattern = r'###\s+(\d{4}-\d{2}-\d{2})\s+—\s+(.+?)(?=###|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for date, body in matches:
            # Extract prevention rule
            prevention = ''
            if '**Prevention Rule:**' in body:
                prevention = body.split('**Prevention Rule:**')[1].split('\n')[0].strip()
            
            errors.append({
                'date': date,
                'content': body.strip(),
                'prevention': prevention
            })
        
        return errors
    
    def _extract_entities(self, content: str) -> List[Dict]:
        """Extract entities from content"""
        entities = []
        
        for entity_type, pattern in self._entity_patterns.items():
            matches = re.findall(pattern, content)
            for match in set(matches):  # Unique
                entities.append({
                    'name': match,
                    'type': entity_type,
                    'confidence': 0.7
                })
        
        return entities
    
    def _extract_tags(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        return re.findall(r'#\w+', content)
    
    def _parse_date_from_filename(self, filename: str) -> str:
        """Extract date from YYYY-MM-DD.md filename"""
        match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
        return match.group(1) if match else ''


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NeuroMemory File System Bridge")
    parser.add_argument("--workspace", default="/root/.openclaw/workspace-ava")
    parser.add_argument("--sync", action="store_true", help="Sync files to memory")
    parser.add_argument("--query", help="Query memory system")
    
    args = parser.parse_args()
    
    async def main():
        bridge = FileSystemBridge(args.workspace)
        await bridge.connect()
        
        try:
            if args.sync:
                results = await bridge.full_sync()
                print(json.dumps(results, indent=2))
            
            if args.query:
                results = await bridge.query_and_update_files(args.query)
                for file, memories in results.items():
                    print(f"\n=== {file} ===")
                    for mem in memories:
                        print(f"  [{mem['importance']:.1f}] {mem['content'][:100]}...")
        finally:
            await bridge.disconnect()
    
    asyncio.run(main())
