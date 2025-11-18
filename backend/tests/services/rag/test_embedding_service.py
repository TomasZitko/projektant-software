"""
Tests for Embedding Service.

Tests vector generation, batch processing, and similarity calculations.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.rag.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    @pytest.fixture
    def mock_openai(self):
        """Mock OpenAI client."""
        with patch('app.services.rag.embedding_service.openai') as mock:
            yield mock

    @pytest.fixture
    def embedding_service(self, mock_openai):
        """Create embedding service with mocked OpenAI."""
        return EmbeddingService(openai_api_key="test-key")

    def test_init(self, embedding_service):
        """Test initialization."""
        assert embedding_service.primary_model == "text-embedding-3-small"
        assert embedding_service.dimensions == 1536
        assert embedding_service.total_tokens == 0
        assert embedding_service.total_requests == 0

    @pytest.mark.asyncio
    async def test_embed_text_success(self, embedding_service, mock_openai):
        """Test successful text embedding."""
        # Mock response
        mock_embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]
        mock_response.usage.total_tokens = 100

        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch('app.services.rag.embedding_service.openai.AsyncOpenAI', return_value=mock_client):
            embedding = await embedding_service.embed_text("Test text")

            assert len(embedding) == 1536
            assert embedding[0] == 0.1
            assert embedding_service.total_tokens == 100
            assert embedding_service.total_requests == 1

    @pytest.mark.asyncio
    async def test_embed_text_wrong_dimensions(self, embedding_service, mock_openai):
        """Test error when embedding has wrong dimensions."""
        # Mock response with wrong dimensions
        mock_embedding = [0.1] * 512  # Wrong size
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]
        mock_response.usage.total_tokens = 100

        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch('app.services.rag.embedding_service.openai.AsyncOpenAI', return_value=mock_client):
            with pytest.raises(ValueError, match="Expected 1536 dimensions"):
                await embedding_service.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_embed_batch_success(self, embedding_service, mock_openai):
        """Test successful batch embedding."""
        texts = ["Text 1", "Text 2", "Text 3"]

        # Mock response
        mock_embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=emb) for emb in mock_embeddings]
        mock_response.usage.total_tokens = 300

        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch('app.services.rag.embedding_service.openai.AsyncOpenAI', return_value=mock_client):
            embeddings = await embedding_service.embed_batch(texts, show_progress=False)

            assert len(embeddings) == 3
            assert len(embeddings[0]) == 1536
            assert embeddings[0][0] == 0.1
            assert embeddings[1][0] == 0.2
            assert embeddings[2][0] == 0.3

    def test_cosine_similarity_identical(self, embedding_service):
        """Test cosine similarity for identical vectors."""
        vec = [1.0, 2.0, 3.0]
        similarity = embedding_service.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self, embedding_service):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 1e-6

    def test_cosine_similarity_opposite(self, embedding_service):
        """Test cosine similarity for opposite vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 1e-6

    def test_cosine_similarity_zero_vector(self, embedding_service):
        """Test cosine similarity with zero vector."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]
        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_batch_cosine_similarity(self, embedding_service):
        """Test batch cosine similarity calculation."""
        query_vec = [1.0, 0.0, 0.0]
        doc_vecs = [
            [1.0, 0.0, 0.0],  # Same direction
            [0.0, 1.0, 0.0],  # Orthogonal
            [-1.0, 0.0, 0.0]  # Opposite
        ]

        similarities = embedding_service.batch_cosine_similarity(query_vec, doc_vecs)

        assert len(similarities) == 3
        assert abs(similarities[0] - 1.0) < 1e-6
        assert abs(similarities[1] - 0.0) < 1e-6
        assert abs(similarities[2] - (-1.0)) < 1e-6

    def test_get_stats(self, embedding_service):
        """Test getting usage statistics."""
        embedding_service.total_tokens = 1000
        embedding_service.total_requests = 10

        stats = embedding_service.get_stats()

        assert stats['total_tokens'] == 1000
        assert stats['total_requests'] == 10
        assert 'estimated_cost_usd' in stats
        assert stats['primary_model'] == 'text-embedding-3-small'
        assert stats['dimensions'] == 1536

    def test_get_stats_cost_calculation(self, embedding_service):
        """Test cost calculation in stats."""
        # text-embedding-3-small costs $0.020 / 1M tokens
        embedding_service.total_tokens = 1_000_000
        embedding_service.total_requests = 100

        stats = embedding_service.get_stats()

        # Should be approximately $0.02
        assert abs(stats['estimated_cost_usd'] - 0.02) < 0.001

    def test_reset_stats(self, embedding_service):
        """Test resetting statistics."""
        embedding_service.total_tokens = 1000
        embedding_service.total_requests = 10

        embedding_service.reset_stats()

        assert embedding_service.total_tokens == 0
        assert embedding_service.total_requests == 0
