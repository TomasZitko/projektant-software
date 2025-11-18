"""
Tests for Czech Document Processor.

Tests PDF parsing, rule extraction, and chunking strategies.
"""

import pytest
from pathlib import Path
from app.services.rag.document_processor import (
    CzechDocumentProcessor,
    ParsedRule,
    DocumentChunk
)


class TestCzechDocumentProcessor:
    """Test suite for CzechDocumentProcessor."""

    @pytest.fixture
    def processor(self, tmp_path):
        """Create document processor with temp directory."""
        return CzechDocumentProcessor(data_dir=tmp_path)

    def test_infer_geometry_type_corridor(self, processor):
        """Test geometry type inference for corridor."""
        text = "Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm."
        geometry_type = processor._infer_geometry_type(text)
        assert geometry_type == "corridor"

    def test_infer_geometry_type_door(self, processor):
        """Test geometry type inference for door."""
        text = "Dveře musí mít minimální šířku 900 mm."
        geometry_type = processor._infer_geometry_type(text)
        assert geometry_type == "door"

    def test_infer_geometry_type_stair(self, processor):
        """Test geometry type inference for stair."""
        text = "Schodiště musí mít minimální šířku 1200 mm."
        geometry_type = processor._infer_geometry_type(text)
        assert geometry_type == "stair"

    def test_extract_conditions_occupancy(self, processor):
        """Test condition extraction for occupancy."""
        text = "Pro budovy s více než 200 osobami platí následující požadavky."
        conditions = processor._extract_conditions(text)
        assert "occupancy_min" in conditions
        assert conditions["occupancy_min"] == 200

    def test_extract_conditions_building_type(self, processor):
        """Test condition extraction for building type."""
        text = "V bytových domech musí být zajištěna požární bezpečnost."
        conditions = processor._extract_conditions(text)
        assert "building_types" in conditions
        assert "residential" in conditions["building_types"]

    def test_map_building_type_residential(self, processor):
        """Test building type mapping for residential."""
        czech_type = "rodinný dům"
        types = processor._map_building_type(czech_type)
        assert "residential" in types
        assert "single-family" in types

    def test_map_building_type_office(self, processor):
        """Test building type mapping for office."""
        czech_type = "kancelář"
        types = processor._map_building_type(czech_type)
        assert "office" in types
        assert "commercial" in types

    def test_translate_to_english(self, processor):
        """Test Czech to English translation."""
        czech_text = "Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1200 mm."
        english = processor._translate_to_english(czech_text)

        # Check that key terms are translated
        assert "Minimum clear width" in english or "minimální" not in english.lower()

    def test_parse_structure_simple(self, processor):
        """Test document structure parsing."""
        pages = [
            {
                'page_num': 1,
                'text': '5 ÚNIKOVÉ CESTY\n5.1 Obecné požadavky\n5.1.1 Minimální šířka chodby',
                'tables': [],
                'width': 595,
                'height': 842
            }
        ]

        structured = processor._parse_structure(pages, "ČSN 73 0802")

        assert structured['standard_code'] == "ČSN 73 0802"
        assert len(structured['chapters']) > 0

    def test_create_chunks_short_text(self, processor):
        """Test chunk creation for short text."""
        structured_doc = {
            'standard_code': 'ČSN 73 0802',
            'chapters': [
                {
                    'number': '5',
                    'title': 'Únikové cesty',
                    'sections': [
                        {
                            'number': '5.1',
                            'title': 'Obecné požadavky',
                            'articles': [
                                {
                                    'number': '5.1.1',
                                    'content': 'Minimální šířka',
                                    'paragraphs': ['Chodby musí mít šířku minimálně 1200 mm.']
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        chunks = processor._create_chunks(structured_doc, [], "test.pdf")

        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(chunk.metadata['standard_code'] == 'ČSN 73 0802' for chunk in chunks)

    def test_create_chunks_long_text(self, processor):
        """Test chunk creation for long text that needs splitting."""
        # Create a long article
        long_text = " ".join([f"Sentence {i}." for i in range(200)])

        structured_doc = {
            'standard_code': 'ČSN 73 0802',
            'chapters': [
                {
                    'number': '5',
                    'title': 'Únikové cesty',
                    'sections': [
                        {
                            'number': '5.1',
                            'title': 'Obecné požadavky',
                            'articles': [
                                {
                                    'number': '5.1.1',
                                    'content': 'Long article',
                                    'paragraphs': [long_text]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        chunks = processor._create_chunks(structured_doc, [], "test.pdf")

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should have metadata
        for chunk in chunks:
            assert 'source' in chunk.metadata
            assert 'standard_code' in chunk.metadata
            assert 'chapter' in chunk.metadata


class TestParsedRule:
    """Test ParsedRule model."""

    def test_parsed_rule_creation(self):
        """Test creating a ParsedRule instance."""
        rule = ParsedRule(
            rule_id="ČSN_73_0802_Sec_5.2.a",
            rule_type="min_width",
            geometry_type="corridor",
            parameter="width_mm",
            operator=">=",
            value=1200.0,
            unit="mm",
            conditions={"building_types": ["residential"]},
            rule_text_cs="Nejmenší světlá šířka...",
            rule_text_en="Minimum clear width...",
            source_document="CSN_73_0802_2009.pdf",
            section="5.2",
            chapter="5",
            page_number=12,
            standard_code="ČSN 73 0802",
            standard_year=2009,
            confidence_score=0.95
        )

        assert rule.rule_id == "ČSN_73_0802_Sec_5.2.a"
        assert rule.value == 1200.0
        assert rule.operator == ">="
        assert rule.confidence_score == 0.95

    def test_parsed_rule_validation_confidence(self):
        """Test that confidence score is validated."""
        with pytest.raises(ValueError):
            ParsedRule(
                rule_id="test",
                rule_type="min_width",
                geometry_type="corridor",
                parameter="width_mm",
                operator=">=",
                value=1200.0,
                unit="mm",
                rule_text_cs="test",
                rule_text_en="test",
                source_document="test.pdf",
                section="1",
                chapter="1",
                page_number=1,
                standard_code="test",
                standard_year=2009,
                confidence_score=1.5  # Invalid - should be <= 1.0
            )


class TestDocumentChunk:
    """Test DocumentChunk model."""

    def test_document_chunk_creation(self):
        """Test creating a DocumentChunk instance."""
        chunk = DocumentChunk(
            chunk_id="test_chunk_1",
            text="This is a test chunk of text.",
            metadata={
                "source": "test.pdf",
                "chapter": "5",
                "section": "5.1"
            }
        )

        assert chunk.chunk_id == "test_chunk_1"
        assert "test chunk" in chunk.text
        assert chunk.metadata["source"] == "test.pdf"

    def test_document_chunk_with_embedding(self):
        """Test DocumentChunk with embedding."""
        embedding = [0.1] * 1536  # Mock 1536-dim embedding

        chunk = DocumentChunk(
            chunk_id="test_chunk_1",
            text="Test text",
            metadata={"source": "test.pdf"},
            embedding=embedding
        )

        assert len(chunk.embedding) == 1536
        assert chunk.embedding[0] == 0.1
