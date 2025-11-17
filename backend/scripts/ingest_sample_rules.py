#!/usr/bin/env python3
"""
Ingest sample Czech building code rules into Pinecone.

This script creates 20+ sample rules from ČSN standards and ingests them
into the vector database for testing the RAG pipeline.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.services.chunking_service import chunking_service, Chunk
from app.services.embedding_service import embedding_service
from app.services.vector_service import vector_service
from app.services.cache_service import cache_service


# Sample Czech building code rules (ČSN standards)
SAMPLE_RULES = [
    # ČSN 73 0802 - Fire Protection
    {
        "rule_id": "ČSN_73_0802_Sec_5.2.a",
        "rule_type": "min_width",
        "geometry_type": "corridor",
        "text": "Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm. "
                "Tato hodnota platí pro budovy s počtem osob do 200. Pro vyšší počty osob "
                "se šířka zvyšuje podle počtu osob.",
        "csn_reference": "ČSN 73 0802",
        "section": "5.2",
        "page": 42,
        "building_types": ["residential", "office", "public"],
    },
    {
        "rule_id": "ČSN_73_0802_Sec_5.2.b",
        "rule_type": "min_width",
        "geometry_type": "corridor",
        "text": "Pro budovy s počtem osob nad 200 musí být šířka únikové cesty alespoň 1 500 mm. "
                "Úniková cesta slouží k evakuaci osob v případě požáru nebo jiné mimořádné události.",
        "csn_reference": "ČSN 73 0802",
        "section": "5.2",
        "page": 42,
        "building_types": ["office", "public", "commercial"],
    },
    {
        "rule_id": "ČSN_73_0802_Sec_5.4.a",
        "rule_type": "min_height",
        "geometry_type": "corridor",
        "text": "Minimální světlá výška únikové cesty nesmí být menší než 2 100 mm. "
                "Tato výška zajišťuje bezpečný průchod osob při evakuaci.",
        "csn_reference": "ČSN 73 0802",
        "section": "5.4",
        "page": 44,
        "building_types": ["residential", "office", "public"],
    },
    {
        "rule_id": "ČSN_73_0802_Sec_6.1.a",
        "rule_type": "min_width",
        "geometry_type": "door",
        "text": "Nejmenší šířka dveří na únikové cestě musí být 800 mm. "
                "Dveře musí být otevíratelné ve směru úniku a nesmí být uzamčeny zevnitř.",
        "csn_reference": "ČSN 73 0802",
        "section": "6.1",
        "page": 48,
        "building_types": ["residential", "office", "public"],
    },
    {
        "rule_id": "ČSN_73_0802_Sec_6.1.b",
        "rule_type": "min_width",
        "geometry_type": "door",
        "text": "Pro veřejné budovy s vyšší kapacitou musí být šířka únikových dveří alespoň 900 mm. "
                "Dveře musí být označeny bezpečnostní signalizací.",
        "csn_reference": "ČSN 73 0802",
        "section": "6.1",
        "page": 48,
        "building_types": ["public", "commercial"],
    },

    # ČSN 73 4301 - Residential Buildings
    {
        "rule_id": "ČSN_73_4301_Sec_4.2.a",
        "rule_type": "min_height",
        "geometry_type": "room",
        "text": "Nejmenší světlá výška obytné místnosti v bytě nesmí být menší než 2 600 mm. "
                "Pro podkrovní místnosti může být výška snížena, musí však činit alespoň 2 300 mm "
                "na ploše minimálně 50% podlahové plochy.",
        "csn_reference": "ČSN 73 4301",
        "section": "4.2",
        "page": 15,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_4301_Sec_4.3.a",
        "rule_type": "min_area",
        "geometry_type": "room",
        "text": "Minimální podlahová plocha obývacího pokoje musí činit 16 m². "
                "Pro garsonky může být tato plocha snížena na 12 m².",
        "csn_reference": "ČSN 73 4301",
        "section": "4.3",
        "page": 16,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_4301_Sec_4.3.b",
        "rule_type": "min_area",
        "geometry_type": "room",
        "text": "Minimální podlahová plocha ložnice musí být 8 m² pro jednolůžkovou "
                "a 12 m² pro dvoulůžkovou ložnici.",
        "csn_reference": "ČSN 73 4301",
        "section": "4.3",
        "page": 16,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_4301_Sec_5.1.a",
        "rule_type": "min_width",
        "geometry_type": "corridor",
        "text": "Šířka chodby v bytě nesmí být menší než 1 100 mm. "
                "Pro jednolůžkové byty může být šířka snížena na 900 mm.",
        "csn_reference": "ČSN 73 4301",
        "section": "5.1",
        "page": 18,
        "building_types": ["residential"],
    },

    # ČSN 73 0580 - Daylight in Buildings
    {
        "rule_id": "ČSN_73_0580_Sec_3.1.a",
        "rule_type": "min_ratio",
        "geometry_type": "window",
        "text": "Poměr prosklené plochy k podlahové ploše obytné místnosti nesmí být menší než 1:10. "
                "Toto zajišťuje dostatečné denní osvětlení.",
        "csn_reference": "ČSN 73 0580",
        "section": "3.1",
        "page": 8,
        "building_types": ["residential", "office"],
    },
    {
        "rule_id": "ČSN_73_0580_Sec_3.2.a",
        "rule_type": "min_ratio",
        "geometry_type": "window",
        "text": "Pro kanceláře musí být poměr prosklené plochy k podlahové ploše alespoň 1:8. "
                "U pracovišť s vysokými nároky na osvětlení může být požadován poměr až 1:6.",
        "csn_reference": "ČSN 73 0580",
        "section": "3.2",
        "page": 9,
        "building_types": ["office"],
    },

    # ČSN 73 0532 - Acoustics
    {
        "rule_id": "ČSN_73_0532_Sec_4.1.a",
        "rule_type": "min_thickness",
        "geometry_type": "wall",
        "text": "Minimální tloušťka příčky mezi byty musí být 150 mm s indexem neprůzvučnosti "
                "Rw alespoň 52 dB. Toto zajišťuje dostatečnou zvukovou izolaci.",
        "csn_reference": "ČSN 73 0532",
        "section": "4.1",
        "page": 12,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_0532_Sec_4.2.a",
        "rule_type": "min_value",
        "geometry_type": "wall",
        "text": "Dělicí stěna mezi bytovou jednotkou a společnými prostory musí mít index "
                "neprůzvučnosti Rw minimálně 47 dB.",
        "csn_reference": "ČSN 73 0532",
        "section": "4.2",
        "page": 13,
        "building_types": ["residential"],
    },

    # ČSN 73 0540 - Thermal Protection
    {
        "rule_id": "ČSN_73_0540_Sec_5.1.a",
        "rule_type": "max_value",
        "geometry_type": "wall",
        "text": "Maximální součinitel prostupu tepla U pro obvodovou stěnu nesmí překročit "
                "0,30 W/(m²·K) pro nové budovy. Pro pasivní domy je požadována hodnota "
                "maximálně 0,15 W/(m²·K).",
        "csn_reference": "ČSN 73 0540",
        "section": "5.1",
        "page": 22,
        "building_types": ["residential", "office", "public"],
    },
    {
        "rule_id": "ČSN_73_0540_Sec_5.2.a",
        "rule_type": "max_value",
        "geometry_type": "window",
        "text": "Součinitel prostupu tepla U oken a dveří nesmí být větší než 1,5 W/(m²·K) "
                "pro standardní výstavbu a 0,8 W/(m²·K) pro nízkoenergetické budovy.",
        "csn_reference": "ČSN 73 0540",
        "section": "5.2",
        "page": 23,
        "building_types": ["residential", "office"],
    },

    # ČSN 73 4130 - Stairs and Ramps
    {
        "rule_id": "ČSN_73_4130_Sec_5.2.a",
        "rule_type": "min_width",
        "geometry_type": "stairs",
        "text": "Minimální šířka schodišťového ramene v bytovém domě musí být 1 100 mm. "
                "Pro rodinné domy je minimální šířka 900 mm.",
        "csn_reference": "ČSN 73 4130",
        "section": "5.2",
        "page": 18,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_4130_Sec_5.3.a",
        "rule_type": "dimension",
        "geometry_type": "stairs",
        "text": "Výška stupně musí být v rozmezí 160 mm až 190 mm, šířka stupně (šlapná plocha) "
                "musí být minimálně 240 mm. Platí vztah 2h + b = 630 mm ± 30 mm, "
                "kde h je výška a b je šířka stupně.",
        "csn_reference": "ČSN 73 4130",
        "section": "5.3",
        "page": 19,
        "building_types": ["residential", "office", "public"],
    },
    {
        "rule_id": "ČSN_73_4130_Sec_6.1.a",
        "rule_type": "min_dimension",
        "geometry_type": "handrail",
        "text": "Zábradlí schodiště musí mít minimální výšku 900 mm měřeno od hrany stupně. "
                "Pro venkovní schodiště a schodiště ve veřejných budovách je minimální výška 1 000 mm.",
        "csn_reference": "ČSN 73 4130",
        "section": "6.1",
        "page": 21,
        "building_types": ["residential", "office", "public"],
    },

    # ČSN 73 6058 - Individual Garages
    {
        "rule_id": "ČSN_73_6058_Sec_4.1.a",
        "rule_type": "min_dimension",
        "geometry_type": "garage",
        "text": "Minimální vnitřní rozměry garáže pro jeden osobní automobil jsou 2 500 mm × 5 000 mm. "
                "Pro pohodlné parkování se doporučuje rozměr 3 000 mm × 6 000 mm.",
        "csn_reference": "ČSN 73 6058",
        "section": "4.1",
        "page": 6,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_6058_Sec_4.2.a",
        "rule_type": "min_height",
        "geometry_type": "garage",
        "text": "Světlá výška garáže musí být minimálně 2 000 mm. "
                "Pro garáže s možností parkování SUV nebo dodávek se doporučuje výška 2 200 mm.",
        "csn_reference": "ČSN 73 6058",
        "section": "4.2",
        "page": 7,
        "building_types": ["residential"],
    },

    # ČSN 73 6110 - Design of Local Roads
    {
        "rule_id": "ČSN_73_6110_Sec_7.2.a",
        "rule_type": "min_width",
        "geometry_type": "road",
        "text": "Minimální šířka obousměrné místní komunikace je 5 500 mm mezi obrubami. "
                "Pro jednosměrné komunikace je minimum 3 000 mm.",
        "csn_reference": "ČSN 73 6110",
        "section": "7.2",
        "page": 28,
        "building_types": ["infrastructure"],
    },

    # Additional rules for better coverage
    {
        "rule_id": "ČSN_73_4301_Sec_6.1.a",
        "rule_type": "min_area",
        "geometry_type": "bathroom",
        "text": "Minimální podlahová plocha koupelny s vanou musí být 3,3 m². "
                "Koupelna pouze se sprchovým koutem může mít plochu 2,5 m².",
        "csn_reference": "ČSN 73 4301",
        "section": "6.1",
        "page": 20,
        "building_types": ["residential"],
    },
    {
        "rule_id": "ČSN_73_0802_Sec_7.1.a",
        "rule_type": "max_distance",
        "geometry_type": "exit",
        "text": "Maximální délka únikové cesty od nejodlehlenějšího místa místnosti "
                "k východu z budovy nesmí překročit 40 m v budovách bez protipožárního zařízení.",
        "csn_reference": "ČSN 73 0802",
        "section": "7.1",
        "page": 52,
        "building_types": ["residential", "office"],
    },
    {
        "rule_id": "ČSN_73_4301_Sec_4.5.a",
        "rule_type": "min_dimension",
        "geometry_type": "balcony",
        "text": "Minimální hloubka balkónu nebo lodžie musí být 1 200 mm. "
                "Doporučená hloubka pro pohodlné užívání je 1 500 mm.",
        "csn_reference": "ČSN 73 4301",
        "section": "4.5",
        "page": 17,
        "building_types": ["residential"],
    },
]


async def main():
    """Main ingestion function."""
    logger.info("=" * 60)
    logger.info("CZECH BUILDING CODE INGESTION SCRIPT")
    logger.info("=" * 60)

    try:
        # Initialize services
        logger.info("Initializing services...")
        await cache_service.connect()
        await embedding_service.initialize()
        await vector_service.initialize()
        logger.info("✓ Services initialized")

        # Prepare chunks
        logger.info(f"\nPreparing {len(SAMPLE_RULES)} sample rules...")
        chunks = []

        for idx, rule in enumerate(SAMPLE_RULES):
            # Create chunk
            chunk_dict = {
                "text": rule["text"],
                "token_count": chunking_service.count_tokens(rule["text"]),
                "char_count": len(rule["text"]),
                "chunk_index": idx,
                "page_number": rule.get("page"),
                "section": rule.get("section"),
                "csn_reference": rule.get("csn_reference"),
                "chunk_type": "rule",
                "rule_id": rule["rule_id"],
                "rule_type": rule.get("rule_type"),
                "geometry_type": rule.get("geometry_type"),
                "building_types": rule.get("building_types", []),
            }

            chunks.append(chunk_dict)

        logger.info(f"✓ Prepared {len(chunks)} chunks")

        # Generate embeddings
        logger.info("\nGenerating embeddings...")
        chunks_with_embeddings = await embedding_service.embed_chunks(chunks, text_field="text")
        logger.info(f"✓ Generated {len(chunks_with_embeddings)} embeddings")

        # Upsert to Pinecone
        logger.info("\nUpserting to Pinecone...")
        upserted_count = await vector_service.upsert_chunks(
            chunks=chunks_with_embeddings,
            namespace="",
            batch_size=50,
            show_progress=True
        )
        logger.info(f"✓ Upserted {upserted_count} vectors")

        # Get final stats
        stats = await vector_service.get_stats()
        logger.info("\n" + "=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total vectors in index: {stats.get('total_vectors', 0)}")
        logger.info(f"Dimension: {stats.get('dimension', 0)}")
        logger.info(f"Embedding stats: {embedding_service.get_stats()}")

        # Test query
        logger.info("\n" + "=" * 60)
        logger.info("TESTING QUERY")
        logger.info("=" * 60)

        test_query = "šířka chodby minimální požadavek residential"
        logger.info(f"Query: '{test_query}'")

        results = await vector_service.query(
            query_text=test_query,
            top_k=3,
            include_metadata=True
        )

        logger.info(f"\nTop {len(results)} results:")
        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            logger.info(f"\n{i}. Score: {result['score']:.3f}")
            logger.info(f"   Rule ID: {metadata.get('csn_reference', 'N/A')}")
            logger.info(f"   Text: {metadata.get('text', 'N/A')[:100]}...")

        logger.info("\n✓ Test query successful!")

    except Exception as e:
        logger.error(f"✗ Ingestion failed: {e}")
        raise

    finally:
        # Cleanup
        logger.info("\nCleaning up...")
        await embedding_service.close()
        await cache_service.disconnect()
        logger.info("✓ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
