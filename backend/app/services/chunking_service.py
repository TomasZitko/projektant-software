"""
Intelligent chunking service for Czech building codes.

Target: 300-500 tokens per chunk with semantic boundary preservation.
Optimized for ČSN standards structure.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import tiktoken
from loguru import logger

from app.config import settings


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    text: str
    token_count: int
    char_count: int
    chunk_index: int
    page_number: Optional[int] = None
    section: Optional[str] = None
    csn_reference: Optional[str] = None
    chunk_type: str = "general"  # general, rule, table, heading
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section,
            "csn_reference": self.csn_reference,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata or {},
        }


class ChunkingService:
    """Intelligent chunking with semantic boundary detection."""

    # Semantic boundaries (in priority order)
    STRONG_BOUNDARIES = [
        r'\n#{1,3}\s+',  # Markdown headers
        r'\n[A-Z][^\n]{0,100}:\s*\n',  # Section headers ending with :
        r'\nČlánek\s+\d+',  # Article markers
        r'\nOddíl\s+\d+',  # Section markers
        r'\nKapitola\s+\d+',  # Chapter markers
        r'\n\d+\.\d+\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]',  # Numbered sections
    ]

    MEDIUM_BOUNDARIES = [
        r'\n\s*\n',  # Double newline (paragraph break)
        r'\.\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]',  # Sentence end followed by capital
        r';\s*\n',  # Semicolon at end of line
    ]

    WEAK_BOUNDARIES = [
        r',\s+',  # Comma with space
        r'\s+',  # Whitespace
    ]

    def __init__(
        self,
        min_chunk_size: int = 300,
        max_chunk_size: int = 500,
        overlap: int = 50,
        model: str = "text-embedding-ada-002"
    ):
        """
        Initialize chunking service.

        Args:
            min_chunk_size: Minimum tokens per chunk
            max_chunk_size: Maximum tokens per chunk
            overlap: Token overlap between chunks
            model: Tokenizer model to use
        """
        self.min_chunk_size = min_chunk_size or settings.MAX_CHUNK_SIZE - 200
        self.max_chunk_size = max_chunk_size or settings.MAX_CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP

        # Initialize tiktoken encoder
        try:
            self.encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found, using cl100k_base")
            self.encoder = tiktoken.get_encoding("cl100k_base")

        logger.info(
            f"ChunkingService initialized: {self.min_chunk_size}-{self.max_chunk_size} tokens, "
            f"overlap={self.overlap}"
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text, disallowed_special=()))

    def split_by_semantic_boundaries(
        self,
        text: str,
        target_size: int
    ) -> List[str]:
        """
        Split text at semantic boundaries.

        Tries strong boundaries first, falls back to weaker ones.
        """
        # If text is already small enough, return it
        if self.count_tokens(text) <= target_size:
            return [text]

        chunks = []

        # Try each boundary level
        for boundaries in [self.STRONG_BOUNDARIES, self.MEDIUM_BOUNDARIES, self.WEAK_BOUNDARIES]:
            # Combine all patterns at this level
            pattern = '|'.join(f'({b})' for b in boundaries)

            try:
                # Split but keep delimiters
                parts = re.split(f'({pattern})', text, flags=re.MULTILINE)

                # Reconstruct with semantic preservation
                current_chunk = ""
                for part in parts:
                    if not part:
                        continue

                    potential_chunk = current_chunk + part
                    token_count = self.count_tokens(potential_chunk)

                    if token_count <= target_size:
                        current_chunk = potential_chunk
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part

                # Add remaining
                if current_chunk:
                    chunks.append(current_chunk)

                # Check if we achieved good chunk sizes
                oversized = sum(1 for c in chunks if self.count_tokens(c) > target_size)
                if oversized / len(chunks) < 0.3:  # Less than 30% oversized
                    return chunks

            except Exception as e:
                logger.warning(f"Boundary split failed: {e}")
                continue

        # Fallback: character-based splitting
        return self._split_by_tokens(text, target_size)

    def _split_by_tokens(self, text: str, target_size: int) -> List[str]:
        """Fallback: Split by token count (preserves words)."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_tokens = 0

        for word in words:
            word_tokens = self.count_tokens(word + " ")

            if current_tokens + word_tokens > target_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap
                overlap_words = int(len(current_chunk) * (self.overlap / target_size))
                current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
                current_tokens = self.count_tokens(" ".join(current_chunk))

            current_chunk.append(word)
            current_tokens += word_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def chunk_document(
        self,
        processed_doc: Dict[str, Any],
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk entire processed document.

        Args:
            processed_doc: Document from DocumentProcessor
            preserve_pages: Keep page boundaries (recommended for ČSN docs)

        Returns:
            List of Chunk objects
        """
        all_chunks = []
        chunk_index = 0

        if preserve_pages:
            # Chunk each page separately
            for page in processed_doc.get("pages", []):
                page_text = page["text"]
                page_num = page["page_number"]
                csn_refs = page.get("csn_references", [])
                sections = page.get("sections", [])

                # Skip empty pages
                if not page_text.strip():
                    continue

                # Split page into semantic chunks
                text_chunks = self.split_by_semantic_boundaries(
                    page_text,
                    self.max_chunk_size
                )

                for text in text_chunks:
                    if not text.strip():
                        continue

                    # Determine chunk type
                    chunk_type = self._classify_chunk(text)

                    chunk = Chunk(
                        text=text.strip(),
                        token_count=self.count_tokens(text),
                        char_count=len(text),
                        chunk_index=chunk_index,
                        page_number=page_num,
                        section=sections[0] if sections else None,
                        csn_reference=csn_refs[0] if csn_refs else None,
                        chunk_type=chunk_type,
                        metadata={
                            "all_csn_refs": csn_refs,
                            "all_sections": sections,
                        }
                    )

                    all_chunks.append(chunk)
                    chunk_index += 1

        else:
            # Chunk entire document as one stream
            full_text = processed_doc.get("full_text", "")
            text_chunks = self.split_by_semantic_boundaries(
                full_text,
                self.max_chunk_size
            )

            for text in text_chunks:
                if not text.strip():
                    continue

                chunk = Chunk(
                    text=text.strip(),
                    token_count=self.count_tokens(text),
                    char_count=len(text),
                    chunk_index=chunk_index,
                    chunk_type=self._classify_chunk(text),
                )

                all_chunks.append(chunk)
                chunk_index += 1

        # Statistics
        avg_tokens = sum(c.token_count for c in all_chunks) / len(all_chunks) if all_chunks else 0
        logger.info(
            f"Created {len(all_chunks)} chunks, "
            f"avg {avg_tokens:.0f} tokens/chunk, "
            f"range {min(c.token_count for c in all_chunks)}-{max(c.token_count for c in all_chunks)}"
        )

        return all_chunks

    def _classify_chunk(self, text: str) -> str:
        """Classify chunk type based on content."""
        # Rule pattern
        if re.search(r'(nejmenší|minimální|maximální|nesmí|musí)', text, re.IGNORECASE):
            return "rule"

        # Table pattern
        if text.count('|') > 5 or text.count('\t') > 5:
            return "table"

        # Heading pattern
        if re.match(r'^[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][^\n]{0,100}:?\s*$', text.strip()):
            return "heading"

        return "general"

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk raw text (convenience method).

        Args:
            text: Raw text to chunk
            metadata: Optional metadata to attach to chunks

        Returns:
            List of Chunk objects
        """
        text_chunks = self.split_by_semantic_boundaries(text, self.max_chunk_size)
        chunks = []

        for idx, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            chunk = Chunk(
                text=chunk_text.strip(),
                token_count=self.count_tokens(chunk_text),
                char_count=len(chunk_text),
                chunk_index=idx,
                chunk_type=self._classify_chunk(chunk_text),
                metadata=metadata,
            )
            chunks.append(chunk)

        return chunks


# Global instance
chunking_service = ChunkingService()
