"""
Vector Store Service

Pinecone-based vector database for building code retrieval.
Optimized for Czech building regulations with hybrid search.

Author: Projektant Copilot Team
License: Commercial
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from pinecone import Pinecone, ServerlessSpec
import asyncio

logger = logging.getLogger(__name__)


class VectorDocument(BaseModel):
    """Document to be stored in vector database."""
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]


class SearchResult(BaseModel):
    """Search result from vector store."""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class VectorStore:
    """
    Production-grade vector store using Pinecone.

    Features:
    - Serverless Pinecone for scalability
    - Metadata filtering for precise retrieval
    - Hybrid search (dense + sparse)
    - Namespace isolation for multi-tenancy
    """

    def __init__(
        self,
        api_key: str,
        environment: str = "us-east-1",
        index_name: str = "projektant-copilot",
        dimension: int = 3072
    ):
        """Initialize Pinecone vector store."""
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.environment = environment
        self.index = None

    async def initialize(self):
        """Initialize or connect to Pinecone index."""
        try:
            # Check if index exists
            existing_indexes = self.pc.list_indexes()

            if self.index_name not in [idx.name for idx in existing_indexes]:
                logger.info(f"Creating new Pinecone index: {self.index_name}")

                # Create serverless index
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.environment
                    )
                )

                # Wait for index to be ready
                await asyncio.sleep(5)

            # Connect to index
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    async def upsert_documents(
        self,
        documents: List[VectorDocument],
        namespace: str = "default",
        batch_size: int = 100
    ):
        """
        Insert or update documents in vector store.

        Args:
            documents: List of documents to upsert
            namespace: Namespace for isolation (e.g., project ID)
            batch_size: Batch size for upsert operations
        """
        if not self.index:
            raise RuntimeError("Vector store not initialized")

        vectors = []
        for doc in documents:
            vectors.append({
                "id": doc.id,
                "values": doc.embedding,
                "metadata": {
                    **doc.metadata,
                    "text": doc.text[:1000]  # Store truncated text in metadata
                }
            })

        # Batch upsert
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(
                vectors=batch,
                namespace=namespace
            )
            logger.info(f"Upserted batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")

        logger.info(f"Upserted {len(documents)} documents to namespace '{namespace}'")

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        namespace: str = "default",
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search vector store for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            namespace: Namespace to search in
            filter_dict: Metadata filters

        Returns:
            List of SearchResults sorted by similarity
        """
        if not self.index:
            raise RuntimeError("Vector store not initialized")

        # Query Pinecone
        response = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            filter=filter_dict,
            include_metadata=True
        )

        # Convert to SearchResults
        results = []
        for match in response.matches:
            results.append(SearchResult(
                id=match.id,
                score=match.score,
                text=match.metadata.get("text", ""),
                metadata={k: v for k, v in match.metadata.items() if k != "text"}
            ))

        logger.info(f"Search returned {len(results)} results")
        return results

    async def search_with_filters(
        self,
        query_embedding: List[float],
        code_type: Optional[str] = None,
        section_id: Optional[str] = None,
        building_type: Optional[str] = None,
        top_k: int = 10,
        namespace: str = "default"
    ) -> List[SearchResult]:
        """
        Search with specific building code filters.

        Args:
            query_embedding: Query vector
            code_type: Filter by code type (e.g., 'ČSN 73 0802')
            section_id: Filter by section (e.g., '5.2.1')
            building_type: Filter by building type (e.g., 'Residential')
            top_k: Number of results
            namespace: Namespace to search

        Returns:
            Filtered search results
        """
        filters = {}

        if code_type:
            filters["code_type"] = code_type

        if section_id:
            filters["section_id"] = {"$gte": section_id}

        if building_type:
            filters["building_type"] = building_type

        return await self.search(
            query_embedding=query_embedding,
            top_k=top_k,
            namespace=namespace,
            filter_dict=filters if filters else None
        )

    async def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace."""
        if not self.index:
            raise RuntimeError("Vector store not initialized")

        self.index.delete(delete_all=True, namespace=namespace)
        logger.info(f"Deleted namespace: {namespace}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.index:
            raise RuntimeError("Vector store not initialized")

        stats = self.index.describe_index_stats()
        return {
            "total_vector_count": stats.total_vector_count,
            "dimension": stats.dimension,
            "index_fullness": stats.index_fullness,
            "namespaces": {ns: data.vector_count for ns, data in stats.namespaces.items()}
        }

    async def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        namespace: str = "default",
        alpha: float = 0.7
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining dense and sparse retrieval.

        Args:
            query_embedding: Dense vector embedding
            query_text: Text for sparse (keyword) search
            top_k: Number of results
            namespace: Namespace to search
            alpha: Weight for dense search (1-alpha for sparse)

        Returns:
            Hybrid search results
        """
        # Dense vector search
        dense_results = await self.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Retrieve more for reranking
            namespace=namespace
        )

        # Sparse keyword search (using metadata text search)
        keywords = query_text.lower().split()
        keyword_filters = {}

        # In production, would use actual BM25 or sparse vectors
        # For now, combine with dense results

        # Score fusion: weighted combination
        final_results = []
        for result in dense_results:
            # Dense score
            dense_score = result.score * alpha

            # Sparse score (simple keyword matching as approximation)
            text_lower = result.text.lower()
            keyword_matches = sum(1 for kw in keywords if kw in text_lower)
            sparse_score = (keyword_matches / len(keywords)) * (1 - alpha)

            # Combined score
            combined_score = dense_score + sparse_score

            final_results.append(SearchResult(
                id=result.id,
                score=combined_score,
                text=result.text,
                metadata=result.metadata
            ))

        # Sort by combined score
        final_results.sort(key=lambda x: x.score, reverse=True)

        return final_results[:top_k]
