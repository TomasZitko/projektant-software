"""
RAG (Retrieval-Augmented Generation) Services for Czech Building Codes.

This package contains the intelligence layer that transforms legal PDFs into
machine-readable rules and enables semantic search over building regulations.

Components:
- DocumentProcessor: PDF → Structured Rules
- EmbeddingService: Text → Vector Embeddings
- VectorStore: Vector Database (Pinecone)
- HybridSearch: Dense + Sparse Retrieval with RRF Fusion
"""

from .document_processor import CzechDocumentProcessor, ParsedRule, DocumentChunk
from .embedding_service import EmbeddingService
from .vector_store import PineconeVectorStore, VectorSearchResult
from .hybrid_search import HybridSearchEngine

__all__ = [
    "CzechDocumentProcessor",
    "ParsedRule",
    "DocumentChunk",
    "EmbeddingService",
    "PineconeVectorStore",
    "VectorSearchResult",
    "HybridSearchEngine",
]
