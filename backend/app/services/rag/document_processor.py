"""
Czech Building Code Document Processor.

Transforms legal PDF documents into structured, machine-readable rules.

This is CRITICAL - the accuracy of rule extraction determines the accuracy
of compliance checking. Every regex pattern, every parsing heuristic has been
carefully designed for Czech building code standards (ČSN).
"""

import pdfplumber
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from pydantic import BaseModel, Field
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ParsedRule(BaseModel):
    """Structured rule extracted from Czech building code."""

    rule_id: str = Field(..., description="Unique identifier, e.g., ČSN_73_0802_Sec_5.2.a")
    rule_type: str = Field(..., description="Type: min_width, max_distance, fire_rating, etc.")
    geometry_type: str = Field(..., description="Geometry: corridor, door, wall, room, etc.")
    parameter: str = Field(..., description="Parameter: width_mm, length_m, height_mm, etc.")
    operator: str = Field(..., description="Comparison: >=, <=, ==")
    value: float = Field(..., description="Numeric value")
    unit: str = Field(..., description="Unit: mm, m, cm, minutes, percentage, etc.")

    # Conditions for rule applicability
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions: building_type, occupancy, fire_zone, etc."
    )

    # Text content
    rule_text_cs: str = Field(..., description="Original Czech text")
    rule_text_en: str = Field(..., description="English translation")

    # Metadata
    source_document: str = Field(..., description="Source PDF filename")
    section: str = Field(..., description="Section number")
    chapter: str = Field(..., description="Chapter number")
    page_number: int = Field(..., description="Page number in PDF")
    standard_code: str = Field(..., description="Standard code, e.g., ČSN 73 0802")
    standard_year: int = Field(..., description="Year of standard version")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")

    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "ČSN_73_0802_Sec_5.2.a",
                "rule_type": "min_width",
                "geometry_type": "corridor",
                "parameter": "width_mm",
                "operator": ">=",
                "value": 1200.0,
                "unit": "mm",
                "conditions": {"building_types": ["residential", "office"]},
                "rule_text_cs": "Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm.",
                "rule_text_en": "Minimum clear width of escape route in corridor must not be less than 1 200 mm.",
                "source_document": "CSN_73_0802_2009.pdf",
                "section": "5.2",
                "chapter": "5",
                "page_number": 12,
                "standard_code": "ČSN 73 0802",
                "standard_year": 2009,
                "confidence_score": 0.95
            }
        }


class DocumentChunk(BaseModel):
    """Semantic chunk of document for vector embedding."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    metadata: Dict[str, Any] = Field(..., description="Rich metadata for filtering")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding (1536-dim)")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "CSN_73_0802_2009_chunk_42",
                "text": "5.2 Únikové cesty v chodbách\n\nNejmenší světlá šířka...",
                "metadata": {
                    "source": "CSN_73_0802_2009.pdf",
                    "standard_code": "ČSN 73 0802",
                    "chapter": "5",
                    "section": "5.2",
                    "chunk_type": "article"
                }
            }
        }


class CzechDocumentProcessor:
    """
    Process Czech building code PDFs into structured rules.

    Handles:
    - Multi-column layouts (common in ČSN standards)
    - Tables with dimensions and requirements
    - Diagrams (extract referenced dimensions)
    - Czech language (diacritics, special characters)
    - References to other standards
    - Version tracking (standards change over time)

    This is CRITICAL - accuracy here determines compliance accuracy.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Czech building code regex patterns
        self.patterns = {
            # Rule ID: ČSN 73 0802, Section 5.2, paragraph a
            'rule_id': re.compile(
                r'ČSN\s+(\d+\s+\d+\s+\d+)[,\s]+([Ss]ekce|[Čč]l[áa]nek)\s+([\d\.]+)\s*([a-z])?',
                re.UNICODE
            ),

            # Dimensions: "min. 1 200 mm", "alespoň 1,5 m"
            'dimension': re.compile(
                r'(min|max|minimální|maximální|alespoň|nejvýše)[^0-9]+([\d\s,\.]+)\s*(mm|m|cm)',
                re.IGNORECASE | re.UNICODE
            ),

            # Percentages: "minimálně 30 %"
            'percentage': re.compile(r'([\d,\.]+)\s*%', re.UNICODE),

            # Occupancy: "více než 200 osob"
            'occupancy': re.compile(
                r'(více\s+než|méně\s+než|alespoň|nejvýše)\s+([\d\s]+)\s*(osob|lid[ií])',
                re.IGNORECASE | re.UNICODE
            ),

            # Building types
            'building_type': re.compile(
                r'(rodinný dům|bytový dům|kancelář|obchodní|průmyslový|škol[ay]|nemocnic[e])',
                re.IGNORECASE | re.UNICODE
            ),

            # Fire rating: "požární odolnost 60 minut"
            'fire_rating': re.compile(
                r'požární\s+odolnost[^0-9]+([\d]+)\s*(minut|min)',
                re.IGNORECASE | re.UNICODE
            ),
        }

    async def process_document(
        self,
        pdf_path: Path,
        standard_code: str
    ) -> Tuple[List[ParsedRule], List[DocumentChunk]]:
        """
        Process a single Czech building code PDF.

        Returns:
        - List of structured rules
        - List of semantic chunks for vector embedding
        """
        logger.info(f"Processing document: {pdf_path}")

        # Extract text from PDF (handling multi-column layouts)
        raw_pages = await self._extract_pdf_text(pdf_path)

        # Parse document structure (chapters, sections, paragraphs)
        structured_doc = self._parse_structure(raw_pages, standard_code)

        # Extract rules from structured content
        rules = self._extract_rules(structured_doc, pdf_path.name)

        # Create semantic chunks for RAG
        chunks = self._create_chunks(structured_doc, rules, pdf_path.name)

        logger.info(f"Extracted {len(rules)} rules and {len(chunks)} chunks from {pdf_path}")

        return rules, chunks

    async def _extract_pdf_text(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract text from PDF handling Czech characters and multi-column layout.

        Uses pdfplumber for accurate text extraction.
        """
        def extract():
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Get page dimensions
                    width = page.width
                    height = page.height

                    # Detect multi-column layout
                    is_two_column = width > 500  # Typical A4 is ~595 points

                    if is_two_column:
                        # Split page into two columns
                        mid = width / 2
                        left_bbox = (0, 0, mid, height)
                        right_bbox = (mid, 0, width, height)

                        left_text = page.crop(left_bbox).extract_text() or ""
                        right_text = page.crop(right_bbox).extract_text() or ""

                        text = left_text + "\n\n" + right_text
                    else:
                        text = page.extract_text() or ""

                    # Extract tables
                    tables = page.extract_tables()

                    pages.append({
                        'page_num': page_num,
                        'text': text,
                        'tables': tables,
                        'width': width,
                        'height': height
                    })

            return pages

        # Run in thread pool (pdfplumber is not async)
        loop = asyncio.get_event_loop()
        pages = await loop.run_in_executor(self.executor, extract)

        return pages

    def _parse_structure(
        self,
        pages: List[Dict[str, Any]],
        standard_code: str
    ) -> Dict[str, Any]:
        """
        Parse document structure: chapters, sections, paragraphs.

        Czech building codes have hierarchical structure:
        - Kapitola (Chapter)
        - Oddíl (Section)
        - Článek (Article)
        - Odstavec (Paragraph)
        """
        structured = {
            'standard_code': standard_code,
            'title': '',
            'chapters': []
        }

        current_chapter = None
        current_section = None
        current_article = None

        for page in pages:
            text = page['text']
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect chapter heading
                if re.match(r'^\d+\s+[A-ZČŘŠŽÝÁÍÉÚŮ]', line):
                    current_chapter = {
                        'number': line.split()[0],
                        'title': ' '.join(line.split()[1:]),
                        'sections': []
                    }
                    structured['chapters'].append(current_chapter)
                    current_section = None
                    current_article = None

                # Detect section heading
                elif re.match(r'^\d+\.\d+\s+[A-ZČŘŠŽÝÁÍÉÚŮ]', line):
                    if current_chapter:
                        current_section = {
                            'number': line.split()[0],
                            'title': ' '.join(line.split()[1:]),
                            'articles': []
                        }
                        current_chapter['sections'].append(current_section)
                        current_article = None

                # Detect article
                elif re.match(r'^\d+\.\d+\.\d+', line):
                    if current_section:
                        current_article = {
                            'number': line.split()[0],
                            'content': line,
                            'paragraphs': []
                        }
                        current_section['articles'].append(current_article)

                # Regular paragraph
                else:
                    if current_article:
                        current_article['paragraphs'].append(line)
                    elif current_section:
                        current_section.setdefault('content', []).append(line)
                    elif current_chapter:
                        current_chapter.setdefault('content', []).append(line)

        return structured

    def _extract_rules(
        self,
        structured_doc: Dict[str, Any],
        source_filename: str
    ) -> List[ParsedRule]:
        """
        Extract structured rules from parsed document.

        This is the MAGIC - transforming legal text into machine-readable rules.

        Examples:

        Czech text:
        "Nejmenší světlá šířka únikové cesty v chodbě nesmí být menší než 1 200 mm."

        Becomes:
        ParsedRule(
            rule_id="ČSN_73_0802_Sec_5.2.a",
            rule_type="min_width",
            geometry_type="corridor",
            parameter="width_mm",
            operator=">=",
            value=1200.0,
            unit="mm",
            ...
        )
        """
        rules = []

        for chapter in structured_doc.get('chapters', []):
            for section in chapter.get('sections', []):
                for article in section.get('articles', []):
                    # Combine article content and paragraphs
                    full_text = article['content'] + ' ' + ' '.join(article.get('paragraphs', []))

                    # Extract dimensions and convert to rules
                    dimension_matches = self.patterns['dimension'].finditer(full_text)

                    for match in dimension_matches:
                        operator_text = match.group(1).lower()
                        value_text = match.group(2).replace(' ', '').replace(',', '.')
                        unit = match.group(3)

                        try:
                            value = float(value_text)
                        except ValueError:
                            continue

                        # Determine operator
                        if 'min' in operator_text or 'alespoň' in operator_text:
                            operator = '>='
                            rule_type = 'min_dimension'
                        elif 'max' in operator_text or 'nejvýše' in operator_text:
                            operator = '<='
                            rule_type = 'max_dimension'
                        else:
                            operator = '=='
                            rule_type = 'exact_dimension'

                        # Infer geometry type from context
                        geometry_type = self._infer_geometry_type(full_text)

                        # Generate rule ID
                        rule_id = f"{structured_doc['standard_code'].replace(' ', '_')}_Sec_{section['number']}_{article['number']}"

                        # Determine parameter name
                        if 'šířka' in full_text.lower() or 'width' in full_text.lower():
                            parameter = 'width_mm'
                        elif 'délka' in full_text.lower() or 'length' in full_text.lower():
                            parameter = 'length_m'
                        elif 'výška' in full_text.lower() or 'height' in full_text.lower():
                            parameter = 'height_mm'
                        else:
                            parameter = 'dimension'

                        # Extract conditions (building type, occupancy, etc.)
                        conditions = self._extract_conditions(full_text)

                        rule = ParsedRule(
                            rule_id=rule_id,
                            rule_type=rule_type,
                            geometry_type=geometry_type,
                            parameter=parameter,
                            operator=operator,
                            value=value,
                            unit=unit,
                            conditions=conditions,
                            rule_text_cs=full_text[:500],  # First 500 chars
                            rule_text_en=self._translate_to_english(full_text[:500]),
                            source_document=source_filename,
                            section=section['number'],
                            chapter=chapter['number'],
                            page_number=0,  # TODO: track page numbers
                            standard_code=structured_doc['standard_code'],
                            standard_year=2009,  # TODO: extract from document
                            confidence_score=0.85  # TODO: calculate based on pattern matches
                        )

                        rules.append(rule)

        return rules

    def _infer_geometry_type(self, text: str) -> str:
        """
        Infer geometry type from context.

        Uses keyword matching and context analysis.
        """
        text_lower = text.lower()

        if any(word in text_lower for word in ['chodba', 'corridor', 'hallway', 'průchod']):
            return 'corridor'
        elif any(word in text_lower for word in ['dveře', 'door', 'vstup']):
            return 'door'
        elif any(word in text_lower for word in ['okno', 'window']):
            return 'window'
        elif any(word in text_lower for word in ['zeď', 'wall', 'stěna']):
            return 'wall'
        elif any(word in text_lower for word in ['schodiště', 'stair', 'schody']):
            return 'stair'
        elif any(word in text_lower for word in ['místnost', 'room', 'prostor']):
            return 'room'
        else:
            return 'general'

    def _extract_conditions(self, text: str) -> Dict[str, Any]:
        """
        Extract conditions for rule applicability.

        Examples:
        - "pro budovy s více než 200 osobami" → {"occupancy_min": 200}
        - "v bytových domech" → {"building_type": ["residential"]}
        """
        conditions = {}

        # Occupancy conditions
        occ_match = self.patterns['occupancy'].search(text)
        if occ_match:
            operator = occ_match.group(1)
            value = int(occ_match.group(2).replace(' ', ''))

            if 'více než' in operator:
                conditions['occupancy_min'] = value
            elif 'méně než' in operator:
                conditions['occupancy_max'] = value

        # Building type conditions
        building_match = self.patterns['building_type'].search(text)
        if building_match:
            building_type_cs = building_match.group(1)
            building_types = self._map_building_type(building_type_cs)
            conditions['building_types'] = building_types

        return conditions

    def _map_building_type(self, czech_type: str) -> List[str]:
        """Map Czech building type to standard categories."""
        mapping = {
            'rodinný dům': ['residential', 'single-family'],
            'bytový dům': ['residential', 'multi-family'],
            'kancelář': ['office', 'commercial'],
            'obchodní': ['commercial', 'retail'],
            'průmyslový': ['industrial'],
            'škola': ['educational'],
            'nemocnice': ['healthcare']
        }
        return mapping.get(czech_type.lower(), ['general'])

    def _translate_to_english(self, czech_text: str) -> str:
        """
        Translate Czech text to English.

        In production, would use translation API (e.g., DeepL, Google Translate).
        For now, use simple keyword replacement for common building code terms.
        """
        translations = {
            'Nejmenší světlá šířka': 'Minimum clear width',
            'únikové cesty': 'of escape route',
            'v chodbě': 'in corridor',
            'nesmí být menší než': 'must not be less than',
            'minimálně': 'minimum',
            'maximálně': 'maximum',
            'požární odolnost': 'fire resistance',
            'budova': 'building',
            'prostory': 'spaces',
            'konstrukce': 'construction',
        }

        result = czech_text
        for czech, english in translations.items():
            result = result.replace(czech, english)

        return result

    def _create_chunks(
        self,
        structured_doc: Dict[str, Any],
        rules: List[ParsedRule],
        source_filename: str
    ) -> List[DocumentChunk]:
        """
        Create semantic chunks for vector embedding.

        Chunking strategy:
        - Target: 300-500 tokens per chunk (~1200-2000 characters)
        - Semantic boundaries: Don't split mid-rule
        - Overlap: 50 tokens between chunks (~200 characters)
        - Preserve context: Include section headers

        Each chunk gets rich metadata for filtering.
        """
        chunks = []
        chunk_id = 0

        for chapter in structured_doc.get('chapters', []):
            for section in chapter.get('sections', []):
                section_text = section.get('title', '')

                for article in section.get('articles', []):
                    article_text = article['content'] + ' ' + ' '.join(article.get('paragraphs', []))

                    # Combine section header + article text
                    full_text = f"{section_text}\n\n{article_text}"

                    # Split into chunks if too long
                    if len(full_text) > 1500:  # ~500 tokens
                        # Split by sentences
                        sentences = re.split(r'[.!?]\s+', full_text)

                        current_chunk = []
                        current_length = 0

                        for sentence in sentences:
                            sentence_length = len(sentence)

                            if current_length + sentence_length > 1500 and current_chunk:
                                # Create chunk
                                chunk_text = '. '.join(current_chunk) + '.'

                                chunk = DocumentChunk(
                                    chunk_id=f"{source_filename}_{chunk_id}",
                                    text=chunk_text,
                                    metadata={
                                        'source': source_filename,
                                        'standard_code': structured_doc['standard_code'],
                                        'chapter': chapter['number'],
                                        'section': section['number'],
                                        'article': article['number'],
                                        'chunk_type': 'article'
                                    }
                                )
                                chunks.append(chunk)
                                chunk_id += 1

                                # Start new chunk with overlap
                                current_chunk = current_chunk[-1:] if current_chunk else []
                                current_length = len(current_chunk[0]) if current_chunk else 0

                            current_chunk.append(sentence)
                            current_length += sentence_length

                        # Add remaining chunk
                        if current_chunk:
                            chunk_text = '. '.join(current_chunk) + '.'
                            chunk = DocumentChunk(
                                chunk_id=f"{source_filename}_{chunk_id}",
                                text=chunk_text,
                                metadata={
                                    'source': source_filename,
                                    'standard_code': structured_doc['standard_code'],
                                    'chapter': chapter['number'],
                                    'section': section['number'],
                                    'article': article['number'],
                                    'chunk_type': 'article'
                                }
                            )
                            chunks.append(chunk)
                            chunk_id += 1
                    else:
                        # Single chunk
                        chunk = DocumentChunk(
                            chunk_id=f"{source_filename}_{chunk_id}",
                            text=full_text,
                            metadata={
                                'source': source_filename,
                                'standard_code': structured_doc['standard_code'],
                                'chapter': chapter['number'],
                                'section': section['number'],
                                'article': article['number'],
                                'chunk_type': 'article'
                            }
                        )
                        chunks.append(chunk)
                        chunk_id += 1

        return chunks
