#!/usr/bin/env python3
"""
Test RAG pipeline end-to-end.

This script tests all components of the RAG pipeline:
1. Cache service
2. Document processor
3. Chunking service
4. Embedding service
5. Vector service
6. Compliance engine
"""

import asyncio
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.services.cache_service import cache_service
from app.services.document_processor import document_processor
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.vector_service import vector_service
from app.services.compliance_engine import compliance_engine


async def test_cache_service():
    """Test cache service."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Cache Service")
    logger.info("=" * 60)

    try:
        await cache_service.connect()

        # Test set/get
        await cache_service.set("test_key", {"value": "test_data"}, ttl=60)
        result = await cache_service.get("test_key")

        assert result is not None, "Cache get failed"
        assert result["value"] == "test_data", "Cache data mismatch"

        # Test stats
        stats = cache_service.get_stats()
        logger.info(f"Cache stats: {stats}")

        logger.info("✓ Cache service test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Cache service test FAILED: {e}")
        return False


async def test_document_processor():
    """Test document processor."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Document Processor")
    logger.info("=" * 60)

    try:
        # Test with sample Czech text
        sample_text = """
        ČSN 73 0802 - Požární bezpečnost staveb

        Článek 5.2
        Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm.
        Tato hodnota platí pro budovy s počtem osob do 200.
        """

        # Test Czech character normalization
        normalized = document_processor.normalize_czech_text(sample_text)

        assert "ČSN" in normalized, "Czech characters lost"
        assert "1 200" in normalized or "1200" in normalized, "Numbers lost"

        logger.info(f"Normalized text length: {len(normalized)} chars")
        logger.info("✓ Document processor test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Document processor test FAILED: {e}")
        return False


async def test_chunking_service():
    """Test chunking service."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Chunking Service")
    logger.info("=" * 60)

    try:
        # Test with sample text
        sample_text = """
        ČSN 73 0802 - Požární bezpečnost staveb

        Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm.

        Pro budovy s počtem osob nad 200 musí být šířka únikové cesty alespoň 1 500 mm.

        Minimální světlá výška únikové cesty nesmí být menší než 2 100 mm.
        """ * 10  # Repeat to create larger text

        chunks = chunking_service.chunk_text(sample_text)

        assert len(chunks) > 0, "No chunks created"
        assert all(300 <= c.token_count <= 500 for c in chunks), "Chunks outside target range"

        logger.info(f"Created {len(chunks)} chunks")
        logger.info(f"Token range: {min(c.token_count for c in chunks)}-{max(c.token_count for c in chunks)}")
        logger.info("✓ Chunking service test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Chunking service test FAILED: {e}")
        return False


async def test_embedding_service():
    """Test embedding service."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Embedding Service")
    logger.info("=" * 60)

    try:
        await embedding_service.initialize()

        # Test single embedding
        text = "Nejmenší šířka chodby nesmí být menší než 1200mm"
        embedding = await embedding_service.embed_text(text)

        assert len(embedding) == 1536, f"Wrong embedding dimension: {len(embedding)}"
        assert all(isinstance(x, float) for x in embedding), "Embedding contains non-float values"

        # Test batch embedding
        texts = [
            "Minimální šířka chodby 1200mm",
            "Výška místnosti 2600mm",
            "Požární bezpečnost únikové cesty"
        ]
        embeddings = await embedding_service.embed_batch(texts)

        assert len(embeddings) == 3, "Batch embedding count mismatch"

        # Test cache (second call should be faster)
        start = time.time()
        cached_embedding = await embedding_service.embed_text(text)
        cache_time = (time.time() - start) * 1000

        assert cache_time < 10, f"Cache too slow: {cache_time:.1f}ms"

        stats = embedding_service.get_stats()
        logger.info(f"Embedding stats: {stats}")
        logger.info("✓ Embedding service test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Embedding service test FAILED: {e}")
        return False


async def test_vector_service():
    """Test vector service."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Vector Service")
    logger.info("=" * 60)

    try:
        await vector_service.initialize()

        # Test query (assumes ingestion has been run)
        results = await vector_service.query(
            query_text="šířka chodby minimální požadavek",
            top_k=3,
            include_metadata=True
        )

        if len(results) == 0:
            logger.warning("⚠️ No results found - have you run ingest_sample_rules.py?")
            logger.warning("Run: python scripts/ingest_sample_rules.py")
            return False

        assert len(results) <= 3, "Too many results returned"
        assert all(0 <= r["score"] <= 1 for r in results), "Invalid scores"

        logger.info(f"Query returned {len(results)} results")
        logger.info(f"Top score: {results[0]['score']:.3f}")

        stats = await vector_service.get_stats()
        logger.info(f"Vector stats: {stats}")
        logger.info("✓ Vector service test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Vector service test FAILED: {e}")
        return False


async def test_compliance_engine():
    """Test compliance engine."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Compliance Engine")
    logger.info("=" * 60)

    try:
        await compliance_engine.initialize()

        # Test case 1: Corridor too narrow (should fail)
        result = await compliance_engine.check_compliance(
            element_type="Wall",
            properties={"width_mm": 1100},
            context={"room_type": "Corridor", "building_type": "Residential"}
        )

        logger.info(f"Test 1 - Narrow corridor:")
        logger.info(f"  Compliant: {result['compliant']}")
        logger.info(f"  Violations: {len(result['violations'])}")
        logger.info(f"  Execution time: {result['execution_time_ms']:.1f}ms")

        # Verify performance
        assert result["execution_time_ms"] < 100, f"Query too slow: {result['execution_time_ms']:.1f}ms"

        # Test case 2: Corridor wide enough (should pass)
        result2 = await compliance_engine.check_compliance(
            element_type="Wall",
            properties={"width_mm": 1300},
            context={"room_type": "Corridor", "building_type": "Residential"}
        )

        logger.info(f"\nTest 2 - Wide corridor:")
        logger.info(f"  Compliant: {result2['compliant']}")
        logger.info(f"  Violations: {len(result2['violations'])}")
        logger.info(f"  Execution time: {result2['execution_time_ms']:.1f}ms")

        # Get stats
        stats = compliance_engine.get_stats()
        logger.info(f"\nEngine stats: {stats}")

        logger.info("✓ Compliance engine test PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ Compliance engine test FAILED: {e}")
        return False


async def test_performance():
    """Test performance targets."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Performance Targets")
    logger.info("=" * 60)

    try:
        # Run multiple queries to test performance
        queries = [
            {"element_type": "Wall", "properties": {"width_mm": 1100}, "context": {"room_type": "Corridor"}},
            {"element_type": "Door", "properties": {"width_mm": 850}, "context": {"room_type": "Office"}},
            {"element_type": "Wall", "properties": {"width_mm": 1400}, "context": {"room_type": "Corridor"}},
        ]

        times = []
        for query in queries:
            start = time.time()
            result = await compliance_engine.check_compliance(**query)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        logger.info(f"Average query time: {avg_time:.1f}ms")
        logger.info(f"P95 query time: {p95_time:.1f}ms")
        logger.info(f"Target: <100ms p95")

        # Check cache hit rate
        cache_stats = cache_service.get_stats()
        hit_rate = cache_stats.get("hit_rate_percent", 0)

        logger.info(f"\nCache hit rate: {hit_rate:.1f}%")
        logger.info(f"Target: >70%")

        # Performance check
        performance_ok = p95_time < 100

        if performance_ok:
            logger.info("✓ Performance targets MET")
        else:
            logger.warning(f"⚠️ Performance targets NOT MET (p95: {p95_time:.1f}ms)")

        return performance_ok

    except Exception as e:
        logger.error(f"✗ Performance test FAILED: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("RAG PIPELINE TEST SUITE")
    logger.info("=" * 60)

    results = {}

    try:
        # Run tests
        results["cache"] = await test_cache_service()
        results["document_processor"] = await test_document_processor()
        results["chunking"] = await test_chunking_service()
        results["embedding"] = await test_embedding_service()
        results["vector"] = await test_vector_service()
        results["compliance"] = await test_compliance_engine()
        results["performance"] = await test_performance()

    except Exception as e:
        logger.error(f"Test suite error: {e}")

    finally:
        # Cleanup
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP")
        logger.info("=" * 60)

        try:
            await compliance_engine.shutdown()
            logger.info("✓ Services shut down")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test_name, passed_flag in results.items():
        status = "✓ PASS" if passed_flag else "✗ FAIL"
        logger.info(f"{test_name:20s}: {status}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.warning(f"\n⚠️ {total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
