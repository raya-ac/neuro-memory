#!/usr/bin/env python3
"""
Working Memory Layer - Redis-based hot cache
Target latency: < 1ms
"""

import json
import time
import redis.asyncio as redis
from typing import List, Optional, Dict, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import AbstractMemoryLayer, MemoryEntry, MemoryLayer
import logging

logger = logging.getLogger("neuro-memory.working")


class WorkingMemoryLayer(AbstractMemoryLayer):
    """
    L1: Working Memory - Ultra-fast Redis cache
    - Max tokens: 8000
    - TTL: 5 minutes default
    - Eviction: LRU
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", max_tokens: int = 8000):
        super().__init__(MemoryLayer.WORKING)
        self.redis_url = redis_url
        self.max_tokens = max_tokens
        self._client: Optional[redis.Redis] = None
        self._token_count = 0
        
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self._client = await redis.from_url(self.redis_url, decode_responses=True)
            await self._client.ping()
            logger.info("Working memory connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
    
    def _key(self, memory_id: str) -> str:
        return f"memory:{memory_id}"
    
    def _token_key(self, memory_id: str) -> str:
        return f"tokens:{memory_id}"
    
    def _context_key(self, session_id: str) -> str:
        return f"context:{session_id}"
    
    def _estimate_tokens(self, content: str) -> int:
        """Rough token estimation (words * 1.3)"""
        return int(len(content.split()) * 1.3)
    
    async def store(self, memory: MemoryEntry, ttl_seconds: int = 300) -> bool:
        """Store memory in working cache with TTL"""
        if not self._client:
            return False
        
        start = time.time()
        try:
            # Check token budget
            tokens = self._estimate_tokens(memory.content)
            if tokens > self.max_tokens * 0.5:  # Don't store huge memories in working
                logger.warning(f"Memory too large for working layer: {tokens} tokens")
                return False
            
            # Store memory
            key = self._key(memory.id)
            data = json.dumps(memory.to_dict())
            
            pipe = self._client.pipeline()
            pipe.setex(key, ttl_seconds, data)
            pipe.setex(self._token_key(memory.id), ttl_seconds, tokens)
            
            # Add to access tracking sorted set
            pipe.zadd("working:access", {memory.id: time.time()})
            
            await pipe.execute()
            
            self._token_count += tokens
            
            # LRU eviction if over budget
            await self._evict_if_needed()
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store in working memory: {e}")
            return False
    
    async def _evict_if_needed(self):
        """LRU eviction when over token budget"""
        if self._token_count <= self.max_tokens:
            return
        
        # Get oldest accessed items
        overflow = self._token_count - self.max_tokens
        to_evict = []
        evicted_tokens = 0
        
        # Get items sorted by last access
        items = await self._client.zrange("working:access", 0, 100, withscores=True)
        
        for memory_id, _ in items:
            if evicted_tokens >= overflow * 1.2:  # Evict 20% extra
                break
            
            token_key = self._token_key(memory_id)
            tokens = await self._client.get(token_key)
            if tokens:
                to_evict.append(memory_id)
                evicted_tokens += int(tokens)
        
        # Delete evicted items
        if to_evict:
            pipe = self._client.pipeline()
            for mid in to_evict:
                pipe.delete(self._key(mid))
                pipe.delete(self._token_key(mid))
                pipe.zrem("working:access", mid)
            await pipe.execute()
            
            self._token_count -= evicted_tokens
            logger.info(f"Evicted {len(to_evict)} items from working memory")
    
    async def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve from working cache"""
        if not self._client:
            return None
        
        start = time.time()
        try:
            key = self._key(memory_id)
            data = await self._client.get(key)
            
            if data:
                # Update access time
                await self._client.zadd("working:access", {memory_id: time.time()})
                
                latency = (time.time() - start) * 1000
                self.record_stat(latency, hit=True)
                return MemoryEntry.from_dict(json.loads(data))
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=False)
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve from working memory: {e}")
            return None
    
    async def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """
        Search working memory (simple text match for hot cache)
        For semantic search, use semantic layer
        """
        if not self._client:
            return []
        
        results = []
        start = time.time()
        
        try:
            # Get all keys
            keys = await self._client.keys("memory:*")
            query_lower = query.lower()
            
            for key in keys[:100]:  # Limit scan
                data = await self._client.get(key)
                if data:
                    memory = MemoryEntry.from_dict(json.loads(data))
                    # Simple text matching
                    if query_lower in memory.content.lower():
                        results.append(memory)
                        if len(results) >= limit:
                            break
            
            latency = (time.time() - start) * 1000
            self.record_stat(latency, hit=len(results) > 0)
            
        except Exception as e:
            logger.error(f"Search failed in working memory: {e}")
        
        return results
    
    async def delete(self, memory_id: str) -> bool:
        """Remove from working cache"""
        if not self._client:
            return False
        
        try:
            pipe = self._client.pipeline()
            pipe.delete(self._key(memory_id))
            pipe.delete(self._token_key(memory_id))
            pipe.zrem("working:access", memory_id)
            await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from working memory: {e}")
            return False
    
    async def warm_cache(self, memory_ids: List[str], layer_retriever):
        """Pre-fetch memories into working cache"""
        for mid in memory_ids:
            if await self._client.exists(self._key(mid)):
                continue  # Already in cache
            
            # Fetch from lower layer
            memory = await layer_retriever(mid)
            if memory:
                await self.store(memory, ttl_seconds=600)  # Longer TTL for pre-fetched
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get working memory statistics"""
        if not self._client:
            return {"status": "disconnected"}
        
        info = await self._client.info("memory")
        keys = await self._client.keys("memory:*")
        
        return {
            "status": "connected",
            "items_in_cache": len(keys),
            "token_count": self._token_count,
            "hit_rate": self.hit_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "redis_memory": info.get("used_memory_human", "unknown")
        }
