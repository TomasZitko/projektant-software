"""
OpenAI embedding service with batching and caching.

Uses text-embedding-ada-002 (1536 dimensions)
Optimized for high-throughput with minimal cost.
"""

import asyncio
from typing import List, Dict, Any, Optional
import hashlib

import openai
from openai import AsyncOpenAI
from loguru import logger

from app.config import settings
from app.services.cache_service import cache_service


class EmbeddingService:
    """High-performance embedding service with caching and batching."""

    # OpenAI limits
    MAX_BATCH_SIZE = 2048  # Max texts per request
    MAX_TOKENS_PER_REQUEST = 8191  # ada-002 limit
    EMBEDDING_DIMENSION = 1536  # ada-002 output dimension

    def __init__(self):
        """Initialize embedding service."""
        self.client: Optional[AsyncOpenAI] = None
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self._total_requests = 0
        self._total_tokens = 0
        self._cache_hits = 0

    async def initialize(self):
        """Initialize OpenAI client."""
        try:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info(f"✓ EmbeddingService initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize OpenAI client: {e}")
            raise

    async def close(self):
        """Close OpenAI client."""
        if self.client:
            await self.client.close()
            logger.info("EmbeddingService closed")

    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for embedding."""
        # Use hash of text + model name
        content = f"{self.model}:{text}"
        hash_digest = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
        return f"emb:{hash_digest}"

    async def embed_text(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cache

        Returns:
            1536-dimensional embedding vector
        """
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache
        if use_cache:
            cache_key = self._generate_cache_key(text)
            cached = await cache_service.get(cache_key)

            if cached:
                self._cache_hits += 1
                logger.debug(f"Cache HIT for embedding (text length: {len(text)})")
                return cached

        # Generate embedding
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            self._total_requests += 1
            self._total_tokens += tokens_used

            # Cache result (TTL: 1 hour)
            if use_cache:
                await cache_service.set(cache_key, embedding, ttl=3600)

            logger.debug(
                f"Generated embedding: {len(text)} chars, "
                f"{tokens_used} tokens, "
                f"{len(embedding)} dims"
            )

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for batch of texts.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            show_progress: Show progress for large batches

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Remove empty texts
        valid_texts = [(i, t) for i, t in enumerate(texts) if t.strip()]

        if not valid_texts:
            raise ValueError("No valid texts to embed")

        # Check cache for each text
        embeddings = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        if use_cache:
            for i, text in valid_texts:
                cache_key = self._generate_cache_key(text)
                cached = await cache_service.get(cache_key)

                if cached:
                    embeddings[i] = cached
                    self._cache_hits += 1
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = [i for i, _ in valid_texts]
            uncached_texts = [t for _, t in valid_texts]

        # Generate embeddings for uncached texts
        if uncached_texts:
            logger.info(
                f"Generating embeddings for {len(uncached_texts)} texts "
                f"({self._cache_hits} cache hits)"
            )

            # Batch into smaller groups (OpenAI limit)
            batch_size = min(self.MAX_BATCH_SIZE, 100)  # Conservative batch size
            batches = [
                uncached_texts[i:i + batch_size]
                for i in range(0, len(uncached_texts), batch_size)
            ]

            all_new_embeddings = []

            for batch_idx, batch in enumerate(batches):
                if show_progress and len(batches) > 1:
                    logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")

                try:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                        encoding_format="float"
                    )

                    batch_embeddings = [item.embedding for item in response.data]
                    tokens_used = response.usage.total_tokens

                    self._total_requests += 1
                    self._total_tokens += tokens_used

                    all_new_embeddings.extend(batch_embeddings)

                    logger.debug(
                        f"Batch {batch_idx + 1}: {len(batch)} embeddings, "
                        f"{tokens_used} tokens"
                    )

                except Exception as e:
                    logger.error(f"Batch embedding failed: {e}")
                    raise

                # Rate limiting (avoid OpenAI throttling)
                if batch_idx < len(batches) - 1:
                    await asyncio.sleep(0.1)

            # Assign new embeddings to results
            for idx, emb_idx in enumerate(uncached_indices):
                embedding = all_new_embeddings[idx]
                embeddings[emb_idx] = embedding

                # Cache new embeddings
                if use_cache:
                    cache_key = self._generate_cache_key(uncached_texts[idx])
                    await cache_service.set(cache_key, embedding, ttl=3600)

        logger.info(
            f"✓ Generated {len(embeddings)} embeddings "
            f"({len(uncached_texts)} new, {self._cache_hits} cached)"
        )

        return embeddings

    async def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
        text_field: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        Embed list of chunk dictionaries.

        Args:
            chunks: List of chunk dicts (must have text_field)
            text_field: Field name containing text to embed

        Returns:
            Chunks with 'embedding' field added
        """
        texts = [chunk[text_field] for chunk in chunks]

        embeddings = await self.embed_batch(texts, use_cache=True, show_progress=True)

        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "cache_hits": self._cache_hits,
            "model": self.model,
            "dimension": self.EMBEDDING_DIMENSION,
        }

    def reset_stats(self):
        """Reset statistics."""
        self._total_requests = 0
        self._total_tokens = 0
        self._cache_hits = 0
        logger.info("Embedding stats reset")


# Global instance
embedding_service = EmbeddingService()
