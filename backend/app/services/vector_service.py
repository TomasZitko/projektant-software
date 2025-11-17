"""
Vector database service for semantic search.
"""
from typing import List, Dict, Any, Optional
from loguru import logger
import asyncio

try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logger.warning("Pinecone not available. Install with: pip install pinecone-client")

from app.config import settings


class VectorService:
    """Service for managing vector embeddings and semantic search."""

    def __init__(self):
        """Initialize vector service with Pinecone."""
        self.api_key = settings.PINECONE_API_KEY
        self.environment = settings.PINECONE_ENVIRONMENT
        self.index_name = settings.PINECONE_INDEX_NAME
        self.dimension = settings.PINECONE_DIMENSION
        self.index = None
        self._initialized = False

    async def initialize(self):
        """Initialize Pinecone connection."""
        if self._initialized:
            return

        if not self.api_key:
            logger.warning("Pinecone API key not configured")
            return

        if not PINECONE_AVAILABLE:
            logger.error("Pinecone package not installed")
            return

        try:
            # Initialize Pinecone
            pc = Pinecone(api_key=self.api_key)

            # Check if index exists
            existing_indexes = pc.list_indexes()
            index_names = [idx.name for idx in existing_indexes]

            if self.index_name not in index_names:
                logger.info(f"Creating Pinecone index: {self.index_name}")
                pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-west-2"
                    )
                )

            # Connect to index
            self.index = pc.Index(self.index_name)
            self._initialized = True
            logger.info(f"Connected to Pinecone index: {self.index_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            self._initialized = False

    async def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = "default",
    ) -> bool:
        """
        Upsert vectors to Pinecone index.

        Args:
            vectors: List of dicts with 'id', 'values', and 'metadata'
            namespace: Pinecone namespace

        Returns:
            Success status
        """
        if not self._initialized:
            await self.initialize()

        if not self.index:
            logger.error("Pinecone index not initialized")
            return False

        try:
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                self.index.upsert(vectors=batch, namespace=namespace)

            logger.info(f"Upserted {len(vectors)} vectors to Pinecone")
            return True

        except Exception as e:
            logger.error(f"Error upserting vectors: {e}")
            return False

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filter_dict: Metadata filters
            namespace: Pinecone namespace

        Returns:
            List of matching results with scores and metadata
        """
        if not self._initialized:
            await self.initialize()

        if not self.index:
            logger.error("Pinecone index not initialized")
            return []

        try:
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter_dict,
                namespace=namespace,
                include_metadata=True,
            )

            matches = []
            for match in results.matches:
                matches.append(
                    {
                        "id": match.id,
                        "score": match.score,
                        "metadata": match.metadata,
                    }
                )

            logger.info(f"Found {len(matches)} matches")
            return matches

        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []

    async def delete_by_ids(
        self,
        ids: List[str],
        namespace: str = "default",
    ) -> bool:
        """Delete vectors by IDs."""
        if not self._initialized:
            await self.initialize()

        if not self.index:
            return False

        try:
            self.index.delete(ids=ids, namespace=namespace)
            logger.info(f"Deleted {len(ids)} vectors")
            return True

        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            return False

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self._initialized:
            await self.initialize()

        if not self.index:
            return {"status": "not_initialized"}

        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "namespaces": stats.namespaces,
            }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"status": "error", "message": str(e)}


# Singleton instance
vector_service = VectorService()
