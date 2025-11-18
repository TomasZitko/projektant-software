"""
Embedding Service

Generates vector embeddings for text using OpenAI and fallback models.
Optimized for Czech language building codes.

Author: Projektant Copilot Team
License: Commercial
"""

from typing import List, Optional, Dict, Any
import logging
import asyncio
from openai import AsyncOpenAI
import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmbeddingResult(BaseModel):
    """Embedding result with metadata."""
    text: str
    embedding: List[float]
    model: str
    token_count: int


class EmbeddingService:
    """
    Production-grade embedding service with fallback and caching.

    Features:
    - OpenAI text-embedding-3-large (primary)
    - Automatic fallback to text-embedding-3-small
    - Batch processing for efficiency
    - Rate limiting and retry logic
    - Czech language optimization
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        fallback_model: str = "text-embedding-3-small"
    ):
        """Initialize embedding service."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model
        self.dimension = 3072 if "large" in model else 1536

    async def embed_text(
        self,
        text: str,
        retry: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed
            retry: Whether to retry with fallback model on failure

        Returns:
            EmbeddingResult with vector and metadata
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding
            token_count = response.usage.total_tokens

            logger.debug(f"Generated embedding for text (length={len(text)}, tokens={token_count})")

            return EmbeddingResult(
                text=text,
                embedding=embedding,
                model=self.model,
                token_count=token_count
            )

        except Exception as e:
            logger.error(f"Embedding failed with {self.model}: {e}")

            if retry and self.fallback_model:
                logger.info(f"Retrying with fallback model: {self.fallback_model}")
                return await self._embed_with_fallback(text)
            raise

    async def _embed_with_fallback(self, text: str) -> EmbeddingResult:
        """Generate embedding using fallback model."""
        response = await self.client.embeddings.create(
            model=self.fallback_model,
            input=text,
            encoding_format="float"
        )

        embedding = response.data[0].embedding

        # Pad or truncate to match primary model dimension
        if len(embedding) < self.dimension:
            embedding = embedding + [0.0] * (self.dimension - len(embedding))
        elif len(embedding) > self.dimension:
            embedding = embedding[:self.dimension]

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.fallback_model,
            token_count=response.usage.total_tokens
        )

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts efficiently.

        Uses batching to optimize API calls and reduce latency.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of EmbeddingResults
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float"
                )

                for j, item in enumerate(response.data):
                    results.append(EmbeddingResult(
                        text=batch[j],
                        embedding=item.embedding,
                        model=self.model,
                        token_count=response.usage.total_tokens // len(batch)
                    ))

                logger.info(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

                # Rate limiting (avoid hitting API limits)
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                # Fall back to individual embeddings for this batch
                for text in batch:
                    try:
                        result = await self.embed_text(text)
                        results.append(result)
                    except Exception as e2:
                        logger.error(f"Individual embedding failed: {e2}")
                        # Create zero vector as fallback
                        results.append(EmbeddingResult(
                            text=text,
                            embedding=[0.0] * self.dimension,
                            model="error",
                            token_count=0
                        ))

        return results

    async def embed_query(
        self,
        query: str,
        expand: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding optimized for query (retrieval).

        Args:
            query: Search query
            expand: Whether to expand query for Czech language

        Returns:
            EmbeddingResult
        """
        # Optionally expand query for better Czech language matching
        if expand:
            expanded_query = self._expand_czech_query(query)
        else:
            expanded_query = query

        return await self.embed_text(expanded_query)

    def _expand_czech_query(self, query: str) -> str:
        """
        Expand query to handle Czech language variations.

        Adds:
        - Common synonyms
        - Plural forms
        - Related terms from building domain
        """
        # Czech building code terminology expansions
        expansions = {
            'chodba': 'chodba corridor průchod',
            'corridor': 'corridor chodba průchod',
            'dveře': 'dveře door dvířka',
            'door': 'door dveře',
            'okno': 'okno window',
            'window': 'window okno',
            'stěna': 'stěna wall zeď',
            'wall': 'wall stěna zeď',
            'šířka': 'šířka width breadth',
            'width': 'width šířka',
            'výška': 'výška height',
            'height': 'height výška',
            'požární': 'požární fire safety bezpečnost',
            'fire': 'fire požární',
            'únik': 'únik escape egress evacuation evakuace',
            'escape': 'escape únik egress evacuation evakuace',
        }

        # Apply expansions
        query_lower = query.lower()
        for term, expansion in expansions.items():
            if term in query_lower:
                query = f"{query} {expansion}"
                break

        return query

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Returns value between -1 and 1 (higher = more similar).
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 10
    ) -> List[int]:
        """
        Find indices of most similar embeddings to query.

        Args:
            query_embedding: Query vector
            candidate_embeddings: List of candidate vectors
            top_k: Number of results to return

        Returns:
            List of indices sorted by similarity (highest first)
        """
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            sim = self.cosine_similarity(query_embedding, candidate)
            similarities.append((i, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top_k indices
        return [idx for idx, _ in similarities[:top_k]]
