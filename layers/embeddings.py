#!/usr/bin/env python3
"""
Embeddings Layer - Vector generation for semantic search
Uses sentence-transformers for embeddings
"""

import numpy as np
from typing import List, Optional, Tuple
import logging
import hashlib

logger = logging.getLogger("neuro-memory.embeddings")

# Lazy load to avoid import errors if not installed
_model = None


def _get_model():
    """Lazy load the embedding model"""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Small, fast model - good enough for memory search
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded embedding model: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed, embeddings disabled")
            _model = False
    return _model if _model else None


def generate_embedding(text: str) -> Optional[np.ndarray]:
    """Generate embedding vector for text"""
    model = _get_model()
    if model is None:
        return None

    # Truncate long texts (model has 256 token limit)
    if len(text) > 1000:
        text = text[:1000]

    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def generate_embeddings(texts: List[str]) -> Optional[np.ndarray]:
    """Generate embeddings for multiple texts (batched, faster)"""
    model = _get_model()
    if model is None:
        return None

    # Truncate long texts
    texts = [t[:1000] if len(t) > 1000 else t for t in texts]

    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings
    except Exception as e:
        logger.error(f"Batch embedding generation failed: {e}")
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    if a is None or b is None:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def cosine_similarity_matrix(query: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
    """Calculate similarity between query and all embeddings"""
    if query is None or embeddings is None or len(embeddings) == 0:
        return np.array([])

    # Normalize vectors
    query_norm = query / np.linalg.norm(query)
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    # Dot product of normalized vectors = cosine similarity
    return np.dot(embeddings_norm, query_norm)


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """Convert embedding to bytes for storage"""
    return embedding.tobytes()


def bytes_to_embedding(data: bytes, dim: int = 384) -> np.ndarray:
    """Convert bytes back to embedding"""
    return np.frombuffer(data, dtype=np.float32).reshape(dim)


def embedding_to_base64(embedding: np.ndarray) -> str:
    """Convert embedding to base64 string for JSON storage"""
    import base64
    return base64.b64encode(embedding.tobytes()).decode('utf-8')


def base64_to_embedding(data: str, dim: int = 384) -> np.ndarray:
    """Convert base64 string back to embedding"""
    import base64
    return np.frombuffer(base64.b64decode(data), dtype=np.float32).reshape(dim)


def get_embedding_dim() -> int:
    """Get embedding dimension"""
    return 384  # all-MiniLM-L6-v2 dimension


class EmbeddingIndex:
    """In-memory embedding index for fast similarity search"""

    def __init__(self):
        self.embeddings = []  # List of (id, embedding) tuples
        self._matrix = None   # Cached numpy matrix

    def add(self, id: str, embedding: np.ndarray):
        """Add embedding to index"""
        if embedding is None:
            return
        self.embeddings.append((id, embedding))
        self._matrix = None  # Invalidate cache

    def remove(self, id: str):
        """Remove embedding from index"""
        self.embeddings = [(i, e) for i, e in self.embeddings if i != id]
        self._matrix = None

    def search(self, query: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Search for k most similar embeddings"""
        if not self.embeddings or query is None:
            return []

        # Build matrix if needed
        if self._matrix is None:
            self._matrix = np.vstack([e for _, e in self.embeddings])

        # Calculate similarities
        similarities = cosine_similarity_matrix(query, self._matrix)

        # Get top k indices
        if len(similarities) == 0:
            return []

        top_k = min(k, len(similarities))
        indices = np.argsort(similarities)[::-1][:top_k]

        # Return (id, score) pairs
        return [(self.embeddings[i][0], float(similarities[i])) for i in indices]

    def clear(self):
        """Clear the index"""
        self.embeddings = []
        self._matrix = None

    def __len__(self):
        return len(self.embeddings)


if __name__ == "__main__":
    # Test
    print("Testing embeddings...")

    texts = [
        "User prefers dark mode and concise responses",
        "Alice works on Project Phoenix with Bob",
        "The API uses Redis for caching",
        "Meeting scheduled for 3pm tomorrow"
    ]

    embeddings = generate_embeddings(texts)

    if embeddings is not None:
        print(f"Generated {len(embeddings)} embeddings of dim {embeddings.shape[1]}")

        # Test similarity
        query = "what does user like"
        query_emb = generate_embedding(query)

        for i, text in enumerate(texts):
            sim = cosine_similarity(query_emb, embeddings[i])
            print(f"  '{text[:40]}...' -> {sim:.3f}")

        # Test index
        print("\nIndex search test:")
        index = EmbeddingIndex()
        for i, emb in enumerate(embeddings):
            index.add(f"mem_{i}", emb)

        results = index.search(query_emb, k=2)
        for id, score in results:
            print(f"  {id}: {score:.3f}")
    else:
        print("Embeddings not available (install sentence-transformers)")
