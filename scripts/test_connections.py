#!/usr/bin/env python3
"""
Test script to verify all service connections.
"""
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import redis
from neo4j import GraphDatabase

# Add parent directory to path
sys.path.insert(0, '../backend')

from app.config import settings


async def test_postgresql():
    """Test PostgreSQL connection."""
    print("Testing PostgreSQL connection...")
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ PostgreSQL connected: {version[:50]}...")
        await engine.dispose()
        return True
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        return False


def test_redis():
    """Test Redis connection."""
    print("\nTesting Redis connection...")
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        print(f"✓ Redis connected")
        r.close()
        return True
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False


def test_neo4j():
    """Test Neo4j connection."""
    print("\nTesting Neo4j connection...")
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            num = result.single()["num"]
            print(f"✓ Neo4j connected (result: {num})")
        driver.close()
        return True
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        return False


def test_api_keys():
    """Check if required API keys are set."""
    print("\nChecking API keys...")
    keys_ok = True

    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
        print("✓ OpenAI API key is set")
    else:
        print("⚠ OpenAI API key not set (required for embeddings)")
        keys_ok = False

    if settings.PINECONE_API_KEY and settings.PINECONE_API_KEY != "your_pinecone_api_key_here":
        print("✓ Pinecone API key is set")
    else:
        print("⚠ Pinecone API key not set (required for vector search)")
        keys_ok = False

    return keys_ok


async def main():
    """Run all connection tests."""
    print("=" * 50)
    print("Projektant Copilot - Connection Tests")
    print("=" * 50)

    results = []

    # Test databases
    results.append(await test_postgresql())
    results.append(test_redis())
    results.append(test_neo4j())

    # Check API keys
    results.append(test_api_keys())

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    if all(results):
        print("✓ All connections successful!")
        return 0
    else:
        print("✗ Some connections failed. Please check configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
