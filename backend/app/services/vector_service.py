"""
Pinecone vector database service with caching and optimized queries.

Index: csn-building-codes
Dimension: 1536 (OpenAI ada-002)
Metric: cosine similarity
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
import time

from pinecone import Pinecone, ServerlessSpec
from loguru import logger

from app.config import settings
from app.services.cache_service import cache_service
from app.services.embedding_service import embedding_service


class VectorService:
    """High-performance vector search with Pinecone."""

    def __init__(self):
        """Initialize vector service."""
        self.pc: Optional[Pinecone] = None
        self.index = None
        self.index_name = settings.PINECONE_INDEX_NAME
        self.dimension = settings.PINECONE_DIMENSION

        self._total_queries = 0
        self._total_upserts = 0
        self._cache_hits = 0

    async def initialize(self):
        """Initialize Pinecone connection and index."""
        try:
            # Initialize Pinecone
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.warning(f"Index '{self.index_name}' not found. Creating...")
                await self.create_index()
            else:
                logger.info(f"✓ Index '{self.index_name}' exists")

            # Connect to index
            self.index = self.pc.Index(self.index_name)

            # Get index stats
            stats = self.index.describe_index_stats()
            logger.info(
                f"✓ Connected to Pinecone index: {self.index_name}, "
                f"vectors: {stats.total_vector_count}, "
                f"dimension: {self.dimension}"
            )

        except Exception as e:
            logger.error(f"✗ Pinecone initialization failed: {e}")
            raise

    async def create_index(
        self,
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1"
    ):
        """
        Create new Pinecone index.

        Args:
            metric: Distance metric (cosine, euclidean, dotproduct)
            cloud: Cloud provider
            region: Cloud region
        """
        try:
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=metric,
                spec=ServerlessSpec(
                    cloud=cloud,
                    region=region
                )
            )

            logger.info(
                f"✓ Created index '{self.index_name}' "
                f"(dimension={self.dimension}, metric={metric})"
            )

            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                logger.info("Waiting for index to be ready...")
                time.sleep(1)

        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            raise

    def _generate_query_cache_key(self, query_vector: List[float], filters: dict, top_k: int) -> str:
        """Generate cache key for vector query."""
        # Create deterministic key from query params
        cache_data = {
            "vector_hash": hashlib.sha256(
                json.dumps(query_vector[:10]).encode()  # Use first 10 dims for hash
            ).hexdigest()[:8],
            "filters": filters,
            "top_k": top_k,
        }
        key_str = json.dumps(cache_data, sort_keys=True)
        return f"vec_query:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    async def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        namespace: str = "",
        batch_size: int = 100,
        show_progress: bool = True
    ) -> int:
        """
        Upsert chunks with embeddings to Pinecone.

        Args:
            chunks: List of chunks with 'embedding' field
            namespace: Pinecone namespace
            batch_size: Vectors per batch
            show_progress: Show progress logs

        Returns:
            Number of vectors upserted
        """
        if not chunks:
            return 0

        total_upserted = 0

        # Prepare vectors for upsert
        vectors = []
        for chunk in chunks:
            if 'embedding' not in chunk:
                logger.warning(f"Chunk {chunk.get('chunk_index')} missing embedding, skipping")
                continue

            # Generate unique ID
            chunk_id = f"chunk_{chunk.get('chunk_index', len(vectors))}_{chunk.get('page_number', 0)}"

            # Prepare metadata (Pinecone has 40KB metadata limit)
            metadata = {
                "text": chunk.get("text", "")[:1000],  # Truncate for metadata size
                "page_number": chunk.get("page_number"),
                "chunk_index": chunk.get("chunk_index"),
                "chunk_type": chunk.get("chunk_type", "general"),
                "token_count": chunk.get("token_count"),
                "section": chunk.get("section", ""),
                "csn_reference": chunk.get("csn_reference", ""),
            }

            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            vectors.append({
                "id": chunk_id,
                "values": chunk["embedding"],
                "metadata": metadata
            })

        # Batch upsert
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]

            try:
                self.index.upsert(
                    vectors=batch,
                    namespace=namespace
                )

                total_upserted += len(batch)
                self._total_upserts += len(batch)

                if show_progress:
                    logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} vectors")

            except Exception as e:
                logger.error(f"Upsert batch failed: {e}")
                raise

        logger.info(f"✓ Upserted {total_upserted} vectors to namespace '{namespace}'")
        return total_upserted

    async def query(
        self,
        query_text: str = None,
        query_vector: List[float] = None,
        top_k: int = None,
        filters: Dict[str, Any] = None,
        namespace: str = "",
        use_cache: bool = True,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Query Pinecone index.

        Args:
            query_text: Text to search (will be embedded)
            query_vector: Pre-computed embedding vector
            top_k: Number of results
            filters: Metadata filters
            namespace: Pinecone namespace
            use_cache: Whether to use cache
            include_metadata: Include metadata in results

        Returns:
            List of matches with score and metadata
        """
        top_k = top_k or settings.TOP_K_RESULTS
        filters = filters or {}

        # Get query vector
        if query_vector is None:
            if query_text is None:
                raise ValueError("Must provide either query_text or query_vector")
            query_vector = await embedding_service.embed_text(query_text)

        # Check cache
        cache_key = None
        if use_cache:
            cache_key = self._generate_query_cache_key(query_vector, filters, top_k)
            cached_results = await cache_service.get(cache_key)

            if cached_results:
                self._cache_hits += 1
                logger.debug(f"Vector query cache HIT (top_k={top_k})")
                return cached_results

        # Execute query
        try:
            start_time = time.time()

            response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filters if filters else None,
                namespace=namespace,
                include_metadata=include_metadata
            )

            query_time = (time.time() - start_time) * 1000  # ms

            self._total_queries += 1

            # Parse results
            results = []
            for match in response.matches:
                result = {
                    "id": match.id,
                    "score": match.score,
                }

                if include_metadata:
                    result["metadata"] = match.metadata

                results.append(result)

            # Cache results (TTL: 1 hour)
            if use_cache and cache_key:
                await cache_service.set(cache_key, results, ttl=3600)

            logger.info(
                f"✓ Vector query: {len(results)} results, "
                f"{query_time:.1f}ms, "
                f"top score: {results[0]['score']:.3f if results else 0}"
            )

            return results

        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            raise

    async def query_by_rule_type(
        self,
        query_text: str,
        rule_type: str = None,
        building_types: List[str] = None,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Query for specific rule types and building types.

        Args:
            query_text: Search query
            rule_type: Filter by rule type (e.g., 'min_width', 'max_height')
            building_types: Filter by building types
            top_k: Number of results

        Returns:
            Matching rules
        """
        filters = {}

        if rule_type:
            filters["chunk_type"] = "rule"

        # Note: Pinecone filters are limited, complex filtering done post-query
        results = await self.query(
            query_text=query_text,
            top_k=top_k or settings.TOP_K_RESULTS * 2,  # Get more for post-filtering
            filters=filters
        )

        # Post-filter results
        filtered_results = []
        for result in results:
            metadata = result.get("metadata", {})

            # Apply additional filters
            if building_types:
                # Check if any building type matches (would need to be in metadata)
                pass  # Implement based on metadata structure

            filtered_results.append(result)

        return filtered_results[:top_k or settings.TOP_K_RESULTS]

    async def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in namespace."""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"✓ Deleted all vectors in namespace '{namespace}'")
            return True
        except Exception as e:
            logger.error(f"Delete namespace failed: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        try:
            stats = self.index.describe_index_stats()

            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "namespaces": {
                    ns: info.vector_count
                    for ns, info in (stats.namespaces or {}).items()
                },
                "queries_executed": self._total_queries,
                "vectors_upserted": self._total_upserts,
                "cache_hits": self._cache_hits,
            }
        except Exception as e:
            logger.error(f"Get stats failed: {e}")
            return {}

    def reset_stats(self):
        """Reset service statistics."""
        self._total_queries = 0
        self._total_upserts = 0
        self._cache_hits = 0
        logger.info("Vector service stats reset")


# Global instance
vector_service = VectorService()
