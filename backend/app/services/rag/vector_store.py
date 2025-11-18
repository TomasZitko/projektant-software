"""
Vector Store using Pinecone for semantic search over building codes.

Manages high-performance vector similarity search with metadata filtering.
"""

from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger(__name__)


class VectorSearchResult(BaseModel):
    """Single search result from vector database."""

    id: str = Field(..., description="Unique document ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    text: Optional[str] = Field(None, description="Original text content")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "CSN_73_0802_chunk_42",
                "score": 0.92,
                "metadata": {
                    "rule_id": "ČSN_73_0802_Sec_5.2.a",
                    "rule_type": "min_width",
                    "geometry_type": "corridor",
                    "building_types": ["residential", "office"]
                },
                "text": "Nejmenší světlá šířka únikové cesty..."
            }
        }


class PineconeVectorStore:
    """
    Pinecone vector database integration.

    Manages:
    - Index creation and configuration
    - Vector upsert with metadata
    - Hybrid search (dense vectors with metadata filtering)
    - Namespace isolation (separate indexes for different standard versions)
    - Batch operations for efficiency

    Pinecone is optimized for:
    - Low-latency search (<100ms)
    - High throughput (1000s QPS)
    - Serverless scaling
    - Production-grade reliability
    """

    def __init__(
        self,
        api_key: str,
        environment: str = "us-east-1",
        index_name: str = "csn-building-codes"
    ):
        """
        Initialize Pinecone vector store.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment/region
            index_name: Name of the index
        """
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name

        self.pc = Pinecone(api_key=api_key)
        self.index = None

        # Stats
        self.total_upserts = 0
        self.total_queries = 0

    async def initialize(self, dimension: int = 1536, metric: str = "cosine"):
        """
        Initialize Pinecone index.

        Creates index if it doesn't exist, otherwise connects to existing.

        Args:
            dimension: Vector dimensions (default 1536 for OpenAI embeddings)
            metric: Distance metric ('cosine', 'euclidean', 'dotproduct')
        """
        try:
            # Check if index exists
            existing_indexes = self.pc.list_indexes()
            index_names = [idx.name for idx in existing_indexes]

            if self.index_name not in index_names:
                # Create index
                logger.info(f"Creating Pinecone index: {self.index_name}")

                self.pc.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric=metric,
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=self.environment
                    )
                )

                logger.info(f"Index {self.index_name} created successfully")

                # Wait for index to be ready
                await asyncio.sleep(5)
            else:
                logger.info(f"Index {self.index_name} already exists")

            # Connect to index
            self.index = self.pc.Index(self.index_name)

            # Log index stats
            stats = self.index.describe_index_stats()
            logger.info(f"Index stats: {stats}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    async def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = "default",
        batch_size: int = 100
    ) -> int:
        """
        Upsert vectors with metadata into Pinecone.

        Each vector should be:
        {
            'id': 'unique_id',
            'values': [0.1, 0.2, ...],  # 1536-dim vector
            'metadata': {
                'text': 'Original text',
                'rule_id': 'ČSN_73_0802_Sec_5.2.a',
                'rule_type': 'min_width',
                'geometry_type': 'corridor',
                'building_types': ['residential', 'office'],
                'standard_code': 'ČSN 73 0802',
                'chapter': '5',
                'section': '5.2',
                ...
            }
        }

        Args:
            vectors: List of vector dictionaries
            namespace: Namespace for isolation (e.g., 'csn-2009', 'csn-2024')
            batch_size: Vectors per batch (max 1000)

        Returns:
            Number of vectors upserted
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        total_upserted = 0

        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]

            try:
                self.index.upsert(
                    vectors=batch,
                    namespace=namespace
                )

                total_upserted += len(batch)
                self.total_upserts += len(batch)

                logger.info(
                    f"Upserted batch {i//batch_size + 1}: "
                    f"{len(batch)} vectors to namespace '{namespace}'"
                )

            except Exception as e:
                logger.error(f"Failed to upsert batch: {e}")
                raise

        logger.info(f"Total upserted: {total_upserted} vectors")
        return total_upserted

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        namespace: str = "default",
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_values: bool = False
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors.

        Supports metadata filtering for precise retrieval:

        Examples:
        ```python
        # Filter by building type
        filter_dict = {
            'building_types': {'$in': ['residential', 'office']}
        }

        # Filter by rule type
        filter_dict = {
            'rule_type': {'$eq': 'min_width'}
        }

        # Combined filters
        filter_dict = {
            '$and': [
                {'building_types': {'$in': ['residential']}},
                {'confidence_score': {'$gte': 0.8}}
            ]
        }
        ```

        Args:
            query_vector: Query embedding (1536-dim)
            top_k: Number of results to return
            namespace: Namespace to search
            filter_dict: Metadata filters (Pinecone filter syntax)
            include_metadata: Include metadata in results
            include_values: Include vector values in results

        Returns:
            List of search results sorted by similarity
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        try:
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter_dict,
                include_metadata=include_metadata,
                include_values=include_values
            )

            search_results = []
            for match in results['matches']:
                result = VectorSearchResult(
                    id=match['id'],
                    score=match['score'],
                    metadata=match.get('metadata', {}),
                    text=match.get('metadata', {}).get('text')
                )
                search_results.append(result)

            self.total_queries += 1

            logger.info(
                f"Found {len(search_results)} results in namespace '{namespace}' "
                f"(filter: {bool(filter_dict)})"
            )

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def search_by_id(
        self,
        ids: List[str],
        namespace: str = "default"
    ) -> List[VectorSearchResult]:
        """
        Fetch vectors by IDs.

        Args:
            ids: List of vector IDs
            namespace: Namespace to search

        Returns:
            List of matching vectors
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        try:
            results = self.index.fetch(ids=ids, namespace=namespace)

            search_results = []
            for vec_id, data in results['vectors'].items():
                result = VectorSearchResult(
                    id=vec_id,
                    score=1.0,  # Perfect match
                    metadata=data.get('metadata', {}),
                    text=data.get('metadata', {}).get('text')
                )
                search_results.append(result)

            logger.info(f"Fetched {len(search_results)} vectors by ID")

            return search_results

        except Exception as e:
            logger.error(f"Fetch by ID failed: {e}")
            raise

    async def delete_vectors(
        self,
        ids: Optional[List[str]] = None,
        delete_all: bool = False,
        namespace: str = "default",
        filter_dict: Optional[Dict[str, Any]] = None
    ):
        """
        Delete vectors from index.

        Args:
            ids: List of IDs to delete
            delete_all: Delete all vectors in namespace
            namespace: Namespace to delete from
            filter_dict: Delete vectors matching filter
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        try:
            self.index.delete(
                ids=ids,
                delete_all=delete_all,
                namespace=namespace,
                filter=filter_dict
            )

            logger.info(f"Deleted vectors from namespace '{namespace}'")

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            raise

    async def delete_namespace(self, namespace: str):
        """
        Delete all vectors in a namespace.

        Args:
            namespace: Namespace to delete
        """
        await self.delete_vectors(delete_all=True, namespace=namespace)

    async def list_namespaces(self) -> List[str]:
        """
        List all namespaces in the index.

        Returns:
            List of namespace names
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        try:
            stats = self.index.describe_index_stats()
            namespaces = list(stats.get('namespaces', {}).keys())

            logger.info(f"Found {len(namespaces)} namespaces")

            return namespaces

        except Exception as e:
            logger.error(f"Failed to list namespaces: {e}")
            raise

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dictionary with index stats (total vectors, dimensions, etc.)
        """
        if not self.index:
            raise RuntimeError("Index not initialized. Call initialize() first.")

        try:
            stats = self.index.describe_index_stats()

            # Format stats
            formatted_stats = {
                'total_vector_count': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', 0),
                'index_fullness': stats.get('index_fullness', 0.0),
                'namespaces': {}
            }

            # Add namespace stats
            for ns, ns_stats in stats.get('namespaces', {}).items():
                formatted_stats['namespaces'][ns] = {
                    'vector_count': ns_stats.get('vector_count', 0)
                }

            return formatted_stats

        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise

    def get_usage_stats(self) -> Dict[str, int]:
        """
        Get usage statistics.

        Returns:
            Dictionary with upserts and queries count
        """
        return {
            'total_upserts': self.total_upserts,
            'total_queries': self.total_queries
        }
