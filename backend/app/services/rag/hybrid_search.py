"""
Hybrid Search Engine combining dense and sparse retrieval.

This is where the MAGIC happens - combining semantic understanding (dense)
with keyword precision (sparse) for optimal retrieval accuracy.

Research shows hybrid search can improve recall by 30-50% over dense-only search.
"""

from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import logging

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search combining:
    1. Dense retrieval (semantic via embeddings)
    2. Sparse retrieval (keyword via BM25/TF-IDF)
    3. Score fusion (RRF - Reciprocal Rank Fusion)

    This SIGNIFICANTLY improves retrieval accuracy:
    - Dense: Catches semantic matches ("corridor width" → "šířka chodby")
    - Sparse: Catches exact terms ("ČSN 73 0802", specific dimensions)
    - Fusion: Best of both worlds

    Example:
    ```python
    # Dense search finds: "escape route width requirements"
    # Sparse search finds: "ČSN 73 0802 section 5.2" (exact code reference)
    # Fusion combines both for comprehensive results
    ```
    """

    def __init__(
        self,
        vector_store,
        embedding_service
    ):
        """
        Initialize hybrid search engine.

        Args:
            vector_store: PineconeVectorStore instance
            embedding_service: EmbeddingService instance
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        # TF-IDF for sparse retrieval
        self.tfidf = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
            stop_words=self._czech_stop_words(),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True  # Use log-scaled TF
        )

        # Document corpus for TF-IDF
        self.corpus_texts = []
        self.corpus_ids = []
        self.corpus_metadata = []
        self.tfidf_fitted = False
        self.tfidf_matrix = None

    def _czech_stop_words(self) -> List[str]:
        """
        Czech stop words for TF-IDF.

        Common Czech words that don't add semantic value.
        """
        return [
            'a', 'aby', 'ale', 'ani', 'ano', 'až', 'bez', 'bude', 'buď',
            'by', 'byl', 'byla', 'bylo', 'byly', 'být', 'co', 'či', 'do',
            'jeho', 'její', 'jejich', 'jen', 'ji', 'jiné', 'již', 'jsem',
            'jsi', 'jsme', 'jsou', 'jste', 'k', 'kam', 'každý', 'kde',
            'kdo', 'když', 'které', 'který', 'která', 'kteří', 'kterou',
            'ma', 'má', 'máte', 'me', 'mě', 'mi', 'mne', 'mně', 'mnou',
            'mohl', 'mohou', 'moje', 'můj', 'mým', 'na', 'nad', 'nám',
            'naši', 'ne', 'nic', 'není', 'nové', 'nový', 'o', 'od', 'ode',
            'pak', 'po', 'pod', 'podle', 'pokud', 'pouze', 'pro', 'před',
            'pře', 'při', 's', 'se', 'si', 'sice', 'své', 'svůj', 'svých',
            'svým', 'svými', 'ta', 'tak', 'také', 'tato', 'té', 'tedy',
            'ten', 'tento', 'tím', 'tímto', 'to', 'tohle', 'toho', 'tohoto',
            'tom', 'tomto', 'tomuto', 'tu', 'ty', 'tyto', 'u', 'už', 'v',
            've', 'velmi', 'více', 'všechen', 'všechno', 'všichni', 'vůči',
            'z', 'za', 'ze', 'že'
        ]

    async def index_corpus(
        self,
        documents: List[Dict[str, Any]],
        show_progress: bool = True
    ):
        """
        Index document corpus for sparse retrieval.

        Args:
            documents: List of documents with format:
                [
                    {
                        'id': 'doc1',
                        'text': '...',
                        'metadata': {...}
                    },
                    ...
                ]
            show_progress: Whether to log progress
        """
        self.corpus_ids = [doc['id'] for doc in documents]
        self.corpus_texts = [doc['text'] for doc in documents]
        self.corpus_metadata = [doc.get('metadata', {}) for doc in documents]

        if show_progress:
            logger.info(f"Fitting TF-IDF on {len(documents)} documents...")

        # Fit TF-IDF
        self.tfidf_matrix = self.tfidf.fit_transform(self.corpus_texts)
        self.tfidf_fitted = True

        if show_progress:
            logger.info(
                f"TF-IDF fitted: {len(self.tfidf.vocabulary_)} unique terms, "
                f"{self.tfidf_matrix.shape[0]} documents"
            )

    async def hybrid_search(
        self,
        query_text: str,
        top_k: int = 20,
        namespace: str = "default",
        filters: Optional[Dict[str, Any]] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search.

        Steps:
        1. Dense search (semantic via vector similarity)
        2. Sparse search (keyword via TF-IDF)
        3. Fuse results using RRF (Reciprocal Rank Fusion)
        4. Return top_k results

        Args:
            query_text: Search query
            top_k: Number of results to return
            namespace: Vector store namespace
            filters: Metadata filters for dense search
            dense_weight: Importance of semantic similarity (0.7 = 70%)
            sparse_weight: Importance of keyword matching (0.3 = 30%)
            min_score: Minimum score threshold

        Returns:
            List of search results with fused scores
        """

        # 1. DENSE SEARCH (Semantic)
        query_embedding = await self.embedding_service.embed_text(query_text)

        dense_results = await self.vector_store.search(
            query_vector=query_embedding,
            top_k=top_k * 2,  # Get more for fusion
            namespace=namespace,
            filter_dict=filters
        )

        logger.info(f"Dense search returned {len(dense_results)} results")

        # 2. SPARSE SEARCH (Keyword)
        sparse_results = []
        if self.tfidf_fitted:
            query_tfidf = self.tfidf.transform([query_text])

            # Calculate cosine similarity with all documents
            scores = (query_tfidf @ self.tfidf_matrix.T).toarray()[0]

            # Get top results
            top_indices = np.argsort(scores)[::-1][:top_k * 2]

            for idx in top_indices:
                if scores[idx] > 0:
                    sparse_results.append({
                        'id': self.corpus_ids[idx],
                        'score': float(scores[idx]),
                        'metadata': self.corpus_metadata[idx],
                        'text': self.corpus_texts[idx]
                    })

            logger.info(f"Sparse search returned {len(sparse_results)} results")
        else:
            logger.warning("TF-IDF not fitted, skipping sparse search")

        # 3. FUSION using RRF
        fused_results = self._reciprocal_rank_fusion(
            dense_results,
            sparse_results,
            dense_weight,
            sparse_weight
        )

        # 4. Filter by minimum score and return top_k
        filtered_results = [r for r in fused_results if r['score'] >= min_score]

        logger.info(
            f"Hybrid search: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(fused_results)} fused → {len(filtered_results)} after filtering"
        )

        return filtered_results[:top_k]

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Any],
        sparse_results: List[Dict[str, Any]],
        dense_weight: float,
        sparse_weight: float,
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) algorithm.

        RRF formula:
        score(d) = Σ (weight_i / (k + rank_i(d)))

        Where:
        - rank_i(d) = position of document d in ranking i (1-indexed)
        - k = constant (typically 60)
        - weight_i = importance of ranking i

        RRF is effective because it:
        - Doesn't require score normalization
        - Handles different score scales gracefully
        - Reduces impact of outliers
        - Simple yet powerful

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            dense_weight: Weight for dense ranking
            sparse_weight: Weight for sparse ranking
            k: RRF constant (default 60)

        Returns:
            Fused results sorted by combined score
        """
        scores = {}

        # Process dense results
        for rank, result in enumerate(dense_results, start=1):
            doc_id = result.id
            rrf_score = dense_weight / (k + rank)

            if doc_id not in scores:
                scores[doc_id] = {
                    'id': doc_id,
                    'score': 0.0,
                    'dense_score': result.score,
                    'sparse_score': 0.0,
                    'dense_rank': rank,
                    'sparse_rank': None,
                    'metadata': result.metadata,
                    'text': result.text
                }

            scores[doc_id]['score'] += rrf_score

        # Process sparse results
        for rank, result in enumerate(sparse_results, start=1):
            doc_id = result['id']
            rrf_score = sparse_weight / (k + rank)

            if doc_id in scores:
                # Document in both rankings - boost score
                scores[doc_id]['score'] += rrf_score
                scores[doc_id]['sparse_score'] = result['score']
                scores[doc_id]['sparse_rank'] = rank
            else:
                # Document only in sparse ranking
                scores[doc_id] = {
                    'id': doc_id,
                    'score': rrf_score,
                    'dense_score': 0.0,
                    'sparse_score': result['score'],
                    'dense_rank': None,
                    'sparse_rank': rank,
                    'metadata': result.get('metadata', {}),
                    'text': result.get('text', '')
                }

        # Sort by fused score
        fused = sorted(scores.values(), key=lambda x: x['score'], reverse=True)

        return fused

    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        namespace: str = "default",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform dense-only semantic search.

        Useful when you want pure semantic matching without keyword bias.

        Args:
            query_text: Search query
            top_k: Number of results
            namespace: Vector store namespace
            filters: Metadata filters

        Returns:
            List of search results
        """
        query_embedding = await self.embedding_service.embed_text(query_text)

        results = await self.vector_store.search(
            query_vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            filter_dict=filters
        )

        # Convert to dict format
        formatted_results = [
            {
                'id': r.id,
                'score': r.score,
                'metadata': r.metadata,
                'text': r.text,
                'dense_score': r.score,
                'sparse_score': 0.0
            }
            for r in results
        ]

        return formatted_results

    async def keyword_search(
        self,
        query_text: str,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Perform sparse-only keyword search.

        Useful for exact term matching (e.g., specific code references).

        Args:
            query_text: Search query
            top_k: Number of results
            min_score: Minimum TF-IDF score

        Returns:
            List of search results
        """
        if not self.tfidf_fitted:
            logger.warning("TF-IDF not fitted, returning empty results")
            return []

        query_tfidf = self.tfidf.transform([query_text])
        scores = (query_tfidf @ self.tfidf_matrix.T).toarray()[0]

        # Get top results
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] >= min_score:
                results.append({
                    'id': self.corpus_ids[idx],
                    'score': float(scores[idx]),
                    'metadata': self.corpus_metadata[idx],
                    'text': self.corpus_texts[idx],
                    'dense_score': 0.0,
                    'sparse_score': float(scores[idx])
                })

        return results

    def get_corpus_stats(self) -> Dict[str, Any]:
        """
        Get statistics about indexed corpus.

        Returns:
            Dictionary with corpus statistics
        """
        if not self.tfidf_fitted:
            return {
                'fitted': False,
                'document_count': 0,
                'vocabulary_size': 0
            }

        return {
            'fitted': True,
            'document_count': len(self.corpus_texts),
            'vocabulary_size': len(self.tfidf.vocabulary_),
            'avg_document_length': np.mean([len(text.split()) for text in self.corpus_texts]),
            'max_document_length': max([len(text.split()) for text in self.corpus_texts]),
            'min_document_length': min([len(text.split()) for text in self.corpus_texts])
        }
