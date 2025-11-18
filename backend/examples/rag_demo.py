"""
RAG Pipeline Demo - Czech Building Codes Intelligence

This demo shows how to:
1. Process Czech building code PDFs into structured rules
2. Generate embeddings for semantic search
3. Store vectors in Pinecone
4. Perform hybrid search (dense + sparse)
5. Retrieve relevant building code regulations

USAGE:
    python examples/rag_demo.py

REQUIREMENTS:
    - OpenAI API key
    - Pinecone API key
    - Sample Czech building code PDF (optional)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rag import (
    CzechDocumentProcessor,
    EmbeddingService,
    PineconeVectorStore,
    HybridSearchEngine
)
from app.core.config import settings


async def demo_document_processing():
    """Demo: Process a Czech building code document."""
    print("=" * 80)
    print("DEMO 1: Document Processing")
    print("=" * 80)

    # Initialize processor
    processor = CzechDocumentProcessor(data_dir=Path("data/building_codes"))

    # Create sample structured document (in production, would parse real PDF)
    sample_doc = {
        'standard_code': 'ČSN 73 0802',
        'title': 'Požární bezpečnost staveb - Společná ustanovení',
        'chapters': [
            {
                'number': '5',
                'title': 'Únikové cesty',
                'sections': [
                    {
                        'number': '5.2',
                        'title': 'Šířka únikových cest',
                        'articles': [
                            {
                                'number': '5.2.1',
                                'content': 'Minimální šířka',
                                'paragraphs': [
                                    'Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm.',
                                    'Pro budovy s více než 200 osobami musí být šířka minimálně 1 500 mm.'
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    # Extract rules
    rules = processor._extract_rules(sample_doc, "CSN_73_0802_2009.pdf")

    print(f"\n✓ Extracted {len(rules)} rules from document")
    if rules:
        print("\nSample Rule:")
        rule = rules[0]
        print(f"  ID: {rule.rule_id}")
        print(f"  Type: {rule.rule_type}")
        print(f"  Geometry: {rule.geometry_type}")
        print(f"  Parameter: {rule.parameter}")
        print(f"  Operator: {rule.operator}")
        print(f"  Value: {rule.value} {rule.unit}")
        print(f"  Czech: {rule.rule_text_cs[:100]}...")
        print(f"  English: {rule.rule_text_en[:100]}...")

    # Create chunks
    chunks = processor._create_chunks(sample_doc, rules, "CSN_73_0802_2009.pdf")

    print(f"\n✓ Created {len(chunks)} semantic chunks")
    if chunks:
        print("\nSample Chunk:")
        chunk = chunks[0]
        print(f"  ID: {chunk.chunk_id}")
        print(f"  Text length: {len(chunk.text)} characters")
        print(f"  Metadata: {chunk.metadata}")

    return rules, chunks


async def demo_embeddings(chunks):
    """Demo: Generate embeddings for text chunks."""
    print("\n" + "=" * 80)
    print("DEMO 2: Embedding Generation")
    print("=" * 80)

    # Check if API key is set
    if not settings.openai_api_key or settings.openai_api_key == "":
        print("\n⚠️  OpenAI API key not set. Skipping embedding demo.")
        print("   Set OPENAI_API_KEY environment variable to run this demo.")
        return []

    # Initialize embedding service
    embedding_service = EmbeddingService(
        openai_api_key=settings.openai_api_key,
        model=settings.openai_embedding_model
    )

    print(f"\n✓ Using model: {embedding_service.primary_model}")

    # Generate embeddings for chunks
    texts = [chunk.text for chunk in chunks[:3]]  # First 3 chunks

    print(f"\n⏳ Generating embeddings for {len(texts)} chunks...")

    embeddings = await embedding_service.embed_batch(texts, show_progress=True)

    print(f"\n✓ Generated {len(embeddings)} embeddings")
    if embeddings:
        print(f"  Dimensions: {len(embeddings[0])}")
        print(f"  Sample values: [{', '.join([f'{v:.4f}' for v in embeddings[0][:5]])}...]")

    # Test similarity
    if len(embeddings) >= 2:
        similarity = embedding_service.cosine_similarity(embeddings[0], embeddings[1])
        print(f"\n✓ Similarity between first two chunks: {similarity:.4f}")

    # Show stats
    stats = embedding_service.get_stats()
    print(f"\n📊 Embedding Stats:")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Estimated cost: ${stats['estimated_cost_usd']:.4f}")

    return embeddings


async def demo_vector_store(chunks, embeddings):
    """Demo: Store and search vectors in Pinecone."""
    print("\n" + "=" * 80)
    print("DEMO 3: Vector Store (Pinecone)")
    print("=" * 80)

    # Check if API key is set
    if not settings.pinecone_api_key or settings.pinecone_api_key == "":
        print("\n⚠️  Pinecone API key not set. Skipping vector store demo.")
        print("   Set PINECONE_API_KEY environment variable to run this demo.")
        return

    # Initialize vector store
    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key,
        environment=settings.pinecone_environment,
        index_name=settings.pinecone_index_name
    )

    print("\n⏳ Initializing Pinecone index...")
    await vector_store.initialize()

    print("✓ Connected to Pinecone")

    # Prepare vectors for upsert
    if embeddings:
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks[:len(embeddings)], embeddings)):
            vector = {
                'id': chunk.chunk_id,
                'values': embedding,
                'metadata': {
                    'text': chunk.text[:1000],  # Truncate for metadata limits
                    **chunk.metadata
                }
            }
            vectors.append(vector)

        print(f"\n⏳ Upserting {len(vectors)} vectors...")
        count = await vector_store.upsert_vectors(vectors, namespace="demo")
        print(f"✓ Upserted {count} vectors")

    # Get stats
    stats = await vector_store.get_index_stats()
    print(f"\n📊 Index Stats:")
    print(f"  Total vectors: {stats['total_vector_count']}")
    print(f"  Dimensions: {stats['dimension']}")
    print(f"  Index fullness: {stats['index_fullness']:.2%}")

    # Search
    if embeddings:
        print("\n⏳ Searching for similar documents...")
        query_vector = embeddings[0]  # Use first embedding as query

        results = await vector_store.search(
            query_vector=query_vector,
            top_k=3,
            namespace="demo"
        )

        print(f"✓ Found {len(results)} results")
        for i, result in enumerate(results, 1):
            print(f"\n  Result {i}:")
            print(f"    ID: {result.id}")
            print(f"    Score: {result.score:.4f}")
            print(f"    Text: {result.text[:100]}..." if result.text else "")


async def demo_hybrid_search(chunks, embeddings):
    """Demo: Hybrid search with RRF fusion."""
    print("\n" + "=" * 80)
    print("DEMO 4: Hybrid Search (Dense + Sparse)")
    print("=" * 80)

    # Check if we have required services
    if not embeddings:
        print("\n⚠️  Embeddings not available. Skipping hybrid search demo.")
        return

    if not settings.openai_api_key or not settings.pinecone_api_key:
        print("\n⚠️  API keys not set. Skipping hybrid search demo.")
        return

    # Initialize services
    embedding_service = EmbeddingService(
        openai_api_key=settings.openai_api_key,
        model=settings.openai_embedding_model
    )

    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key,
        environment=settings.pinecone_environment,
        index_name=settings.pinecone_index_name
    )
    await vector_store.initialize()

    # Initialize hybrid search
    hybrid_search = HybridSearchEngine(
        vector_store=vector_store,
        embedding_service=embedding_service
    )

    # Index corpus for sparse search
    documents = [
        {
            'id': chunk.chunk_id,
            'text': chunk.text,
            'metadata': chunk.metadata
        }
        for chunk in chunks
    ]

    print("\n⏳ Indexing corpus for sparse search...")
    await hybrid_search.index_corpus(documents)

    stats = hybrid_search.get_corpus_stats()
    print(f"\n✓ Indexed corpus:")
    print(f"  Documents: {stats['document_count']}")
    print(f"  Vocabulary size: {stats['vocabulary_size']}")

    # Perform hybrid search
    query = "Jaká je minimální šířka chodby?"  # "What is the minimum corridor width?"

    print(f"\n🔍 Query: {query}")
    print("\n⏳ Performing hybrid search...")

    results = await hybrid_search.hybrid_search(
        query_text=query,
        top_k=5,
        namespace="demo",
        dense_weight=0.7,
        sparse_weight=0.3
    )

    print(f"\n✓ Found {len(results)} results")

    for i, result in enumerate(results, 1):
        print(f"\n  Result {i}:")
        print(f"    Score: {result['score']:.4f}")
        print(f"    Dense score: {result['dense_score']:.4f}")
        print(f"    Sparse score: {result['sparse_score']:.4f}")
        print(f"    Text: {result['text'][:150]}..." if result.get('text') else "")


async def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("RAG PIPELINE DEMO - Czech Building Codes Intelligence")
    print("=" * 80)

    # Demo 1: Document processing
    rules, chunks = await demo_document_processing()

    # Demo 2: Embeddings
    embeddings = await demo_embeddings(chunks)

    # Demo 3: Vector store
    await demo_vector_store(chunks, embeddings)

    # Demo 4: Hybrid search
    await demo_hybrid_search(chunks, embeddings)

    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Add your own Czech building code PDFs to data/building_codes/")
    print("2. Set up OpenAI and Pinecone API keys in .env")
    print("3. Run the full ingestion pipeline")
    print("4. Build the FastAPI endpoints for compliance checking")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
