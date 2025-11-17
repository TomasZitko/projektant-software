"""
PDF document processor optimized for Czech building codes (ČSN standards).

Handles:
- Czech characters (ě, š, č, ř, ž, ý, á, í, é, ú, ů, ť, ď, ň)
- Multi-column layouts
- Tables and structured data
- Page metadata extraction
"""

import re
from typing import List, Dict, Any
from pathlib import Path

import pymupdf  # PyMuPDF for robust PDF parsing
import pdfplumber
from loguru import logger


class DocumentProcessor:
    """High-performance PDF processor for Czech building codes."""

    # Czech ČSN standard patterns
    CSN_PATTERN = re.compile(r'ČSN\s+\d+\s+\d+(?:\s+\d+)?')
    SECTION_PATTERN = re.compile(r'(?:Článek|Oddíl|Kapitola)\s+\d+(?:\.\d+)*')

    # Measurement patterns
    MEASUREMENT_PATTERN = re.compile(
        r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(mm|cm|m|m²|m³|%|°C|kg|kN)',
        re.IGNORECASE
    )

    def __init__(self):
        """Initialize document processor."""
        self.supported_extensions = {'.pdf'}

    def extract_text_pymupdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract text using PyMuPDF (faster, better Czech support).

        Returns list of page dictionaries with text and metadata.
        """
        pages = []

        try:
            doc = pymupdf.open(pdf_path)

            for page_num, page in enumerate(doc, start=1):
                # Extract text with layout preservation
                text = page.get_text("text", sort=True)

                # Extract metadata
                metadata = {
                    "page": page_num,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                }

                # Extract links and references
                links = [link.get('uri', '') for link in page.get_links() if link.get('uri')]

                # Find ČSN references
                csn_refs = self.CSN_PATTERN.findall(text)
                sections = self.SECTION_PATTERN.findall(text)

                pages.append({
                    "page_number": page_num,
                    "text": text.strip(),
                    "char_count": len(text),
                    "csn_references": list(set(csn_refs)),
                    "sections": list(set(sections)),
                    "links": links,
                    "metadata": metadata,
                })

            doc.close()
            logger.info(f"Extracted {len(pages)} pages from {pdf_path.name} using PyMuPDF")

        except Exception as e:
            logger.error(f"PyMuPDF extraction failed for {pdf_path}: {e}")
            raise

        return pages

    def extract_tables_pdfplumber(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tables using pdfplumber (better table detection).

        Returns list of tables per page.
        """
        all_tables = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()

                    if tables:
                        for table_idx, table in enumerate(tables):
                            all_tables.append({
                                "page": page_num,
                                "table_index": table_idx,
                                "rows": len(table),
                                "cols": len(table[0]) if table else 0,
                                "data": table,
                            })

            logger.info(f"Extracted {len(all_tables)} tables from {pdf_path.name}")

        except Exception as e:
            logger.warning(f"Table extraction failed for {pdf_path}: {e}")
            # Non-critical, continue without tables

        return all_tables

    def process_pdf(
        self,
        pdf_path: Path,
        extract_tables: bool = True
    ) -> Dict[str, Any]:
        """
        Process complete PDF document.

        Args:
            pdf_path: Path to PDF file
            extract_tables: Whether to extract tables (slower but more complete)

        Returns:
            Dictionary with processed content and metadata
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {pdf_path.suffix}")

        logger.info(f"Processing PDF: {pdf_path.name}")

        # Extract text content
        pages = self.extract_text_pymupdf(pdf_path)

        # Extract tables if requested
        tables = []
        if extract_tables:
            tables = self.extract_tables_pdfplumber(pdf_path)

        # Combine all text
        full_text = "\n\n".join([p["text"] for p in pages])

        # Extract all ČSN references
        all_csn_refs = set()
        for page in pages:
            all_csn_refs.update(page["csn_references"])

        # Extract measurements
        measurements = self.MEASUREMENT_PATTERN.findall(full_text)

        # Document metadata
        metadata = {
            "filename": pdf_path.name,
            "path": str(pdf_path),
            "page_count": len(pages),
            "total_chars": len(full_text),
            "total_words": len(full_text.split()),
            "csn_references": sorted(all_csn_refs),
            "table_count": len(tables),
            "measurement_count": len(measurements),
        }

        result = {
            "metadata": metadata,
            "full_text": full_text,
            "pages": pages,
            "tables": tables,
            "csn_references": sorted(all_csn_refs),
        }

        logger.info(
            f"✓ Processed {metadata['page_count']} pages, "
            f"{metadata['total_words']} words, "
            f"{len(all_csn_refs)} ČSN refs"
        )

        return result

    def extract_rules(self, processed_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract structured rules from processed document.

        Identifies rule patterns like:
        - "Nejmenší šířka ... nesmí být menší než X mm"
        - "Minimální výška ... musí být alespoň X m"
        - "Požadovaná hodnota ... činí X"
        """
        rules = []

        # Rule patterns (Czech building code language)
        rule_patterns = [
            # Minimum requirements
            (
                r'([Nn]ejmenší|[Mm]inimální)\s+([^\n]{10,80}?)\s+(nesmí být menší než|musí být alespoň|činí)\s+' +
                r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(mm|cm|m|m²|m³)',
                "minimum"
            ),
            # Maximum requirements
            (
                r'([Nn]ejvětší|[Mm]aximální)\s+([^\n]{10,80}?)\s+(nesmí být větší než|nesmí překročit|činí)\s+' +
                r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(mm|cm|m|m²|m³)',
                "maximum"
            ),
            # Range requirements
            (
                r'([^\n]{10,80}?)\s+musí být v rozmezí\s+' +
                r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(mm|cm|m|m²|m³)?\s+až\s+' +
                r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(mm|cm|m|m²|m³)',
                "range"
            ),
        ]

        for page in processed_doc["pages"]:
            text = page["text"]
            page_num = page["page_number"]

            for pattern, rule_type in rule_patterns:
                matches = re.finditer(pattern, text, re.MULTILINE | re.UNICODE)

                for match in matches:
                    # Extract context (surrounding text)
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end].strip()

                    rules.append({
                        "rule_type": rule_type,
                        "match_text": match.group(0),
                        "context": context,
                        "page": page_num,
                        "csn_references": page.get("csn_references", []),
                    })

        logger.info(f"Extracted {len(rules)} rule patterns from document")
        return rules

    def normalize_czech_text(self, text: str) -> str:
        """
        Normalize Czech text for better processing.

        - Remove extra whitespace
        - Normalize quotes
        - Fix common OCR errors
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Common OCR fixes for Czech
        ocr_fixes = {
            'č': ['c̆', 'ĉ'],
            'š': ['s̆', 'ŝ'],
            'ř': ['r̆', 'ř'],
            'ž': ['z̆', 'ẑ'],
        }

        for correct, variants in ocr_fixes.items():
            for variant in variants:
                text = text.replace(variant, correct)

        return text.strip()


# Global instance
document_processor = DocumentProcessor()
