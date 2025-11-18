"""
Embedding Service for generating vector representations of text.

Supports multiple embedding models with automatic fallback for resilience.
Uses OpenAI's state-of-the-art embedding models for semantic understanding.
"""

import openai
from typing import List, Dict, Any, Optional
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import asyncio

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generate vector embeddings for text.

    Supports multiple embedding models with fallback:
    1. OpenAI text-embedding-3-small (primary) - 1536 dimensions, cheaper
    2. OpenAI text-embedding-ada-002 (fallback) - 1536 dimensions
    3. Configurable batch processing for cost optimization

    Features:
    - Async batch processing
    - Automatic retry with exponential backoff
    - Cost tracking
    - Rate limiting
    """

    def __init__(
        self,
        openai_api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536
    ):
        """
        Initialize embedding service.

        Args:
            openai_api_key: OpenAI API key
            model: Embedding model name
            dimensions: Vector dimensions (default 1536)
        """
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key

        self.primary_model = model
        self.fallback_model = "text-embedding-ada-002"
        self.dimensions = dimensions

        # Cost tracking
        self.total_tokens = 0
        self.total_requests = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Vector embedding (1536-dimensional)

        Raises:
            Exception: If embedding generation fails after retries
        """
        try:
            # Use new OpenAI client API (v1.0+)
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            response = await client.embeddings.create(
                input=text,
                model=self.primary_model
            )

            embedding = response.data[0].embedding

            if len(embedding) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(embedding)}")

            # Update stats
            self.total_tokens += response.usage.total_tokens
            self.total_requests += 1

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding with {self.primary_model}: {e}")

            # Try fallback model
            try:
                client = openai.AsyncOpenAI(api_key=self.openai_api_key)

                response = await client.embeddings.create(
                    input=text,
                    model=self.fallback_model
                )

                embedding = response.data[0].embedding

                self.total_tokens += response.usage.total_tokens
                self.total_requests += 1

                logger.info(f"Successfully used fallback model: {self.fallback_model}")

                return embedding

            except Exception as e2:
                logger.error(f"Fallback embedding also failed: {e2}")
                raise

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Processes in batches to optimize API usage and cost.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (max 2048 for OpenAI)
            show_progress: Whether to log progress

        Returns:
            List of embeddings (same order as input texts)
        """
        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_num = i // batch_size + 1

            try:
                client = openai.AsyncOpenAI(api_key=self.openai_api_key)

                response = await client.embeddings.create(
                    input=batch,
                    model=self.primary_model
                )

                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)

                # Update stats
                self.total_tokens += response.usage.total_tokens
                self.total_requests += 1

                if show_progress:
                    logger.info(
                        f"Batch {batch_num}/{total_batches}: "
                        f"Generated {len(batch_embeddings)} embeddings "
                        f"({response.usage.total_tokens} tokens)"
                    )

            except Exception as e:
                logger.error(f"Batch embedding failed for batch {batch_num}: {e}")

                # Fall back to individual embeddings for this batch
                logger.warning(f"Falling back to individual embeddings for batch {batch_num}")

                for text in batch:
                    try:
                        embedding = await self.embed_text(text)
                        embeddings.append(embedding)
                    except Exception as e2:
                        logger.error(f"Failed to embed text even individually: {e2}")
                        # Add zero vector as placeholder
                        embeddings.append([0.0] * self.dimensions)

            # Small delay to avoid rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        return embeddings

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score in range [-1, 1]
            1 = identical, 0 = orthogonal, -1 = opposite
        """
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def batch_cosine_similarity(
        self,
        query_vec: List[float],
        doc_vecs: List[List[float]]
    ) -> List[float]:
        """
        Calculate cosine similarity between query and multiple documents.

        Optimized using numpy for batch computation.

        Args:
            query_vec: Query vector
            doc_vecs: List of document vectors

        Returns:
            List of similarity scores
        """
        query_np = np.array(query_vec)
        docs_np = np.array(doc_vecs)

        # Normalize query
        query_norm = query_np / np.linalg.norm(query_np)

        # Normalize documents
        docs_norm = docs_np / np.linalg.norm(docs_np, axis=1, keepdims=True)

        # Compute similarities
        similarities = np.dot(docs_norm, query_norm)

        return similarities.tolist()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.

        Returns:
            Dictionary with tokens used, requests made, estimated cost
        """
        # OpenAI pricing (as of 2024):
        # text-embedding-3-small: $0.020 / 1M tokens
        # text-embedding-ada-002: $0.100 / 1M tokens

        cost_per_million = 0.020 if self.primary_model == "text-embedding-3-small" else 0.100
        estimated_cost = (self.total_tokens / 1_000_000) * cost_per_million

        return {
            'total_tokens': self.total_tokens,
            'total_requests': self.total_requests,
            'estimated_cost_usd': round(estimated_cost, 4),
            'primary_model': self.primary_model,
            'fallback_model': self.fallback_model,
            'dimensions': self.dimensions
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.total_tokens = 0
        self.total_requests = 0
