"""Shared pydantic data models used across ingestion, retrieval, and generation."""
from __future__ import annotations

import hashlib
from typing import Literal, Optional

from pydantic import BaseModel, Field

ChunkType = Literal["section", "subsection", "definition", "schedule", "page"]


def content_hash(text: str) -> str:
    """Stable sha256 of text; used for chunk ids and embedding cache keys."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- Ingestion ----------

class StatuteSection(BaseModel):
    """A parsed section of a statute (parser output, pre-chunking)."""

    statute_key: str
    statute_title: str
    section_number: str
    section_heading: str = ""
    text: str
    subsections: list[str] = Field(default_factory=list)
    is_definitions: bool = False


class Chunk(BaseModel):
    """An embeddable unit with citation metadata (chunker output)."""

    chunk_id: str
    statute_key: str
    statute_title: str
    section_number: str
    section_heading: str = ""
    chunk_type: ChunkType = "section"
    text: str
    char_count: int = 0

    @classmethod
    def build(cls, *, statute_key: str, statute_title: str, section_number: str,
              section_heading: str, chunk_type: ChunkType, text: str) -> "Chunk":
        return cls(
            chunk_id=content_hash(text),
            statute_key=statute_key,
            statute_title=statute_title,
            section_number=section_number,
            section_heading=section_heading,
            chunk_type=chunk_type,
            text=text,
            char_count=len(text),
        )


# ---------- Retrieval ----------

class RetrievalFilters(BaseModel):
    """Payload filters applied at search time."""

    statute: Optional[str] = None            # statute_key
    section: Optional[str] = None            # section_number
    chunk_type: Optional[list[ChunkType]] = None


class RetrievedChunk(BaseModel):
    """A chunk returned from retrieval, with its score and source id."""

    source_id: str            # short human/citation id, e.g. "S1"
    chunk_id: str
    statute_key: str
    statute_title: str
    section_number: str
    section_heading: str = ""
    chunk_type: ChunkType = "section"
    text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"{self.statute_title} — Section {self.section_number}"


# ---------- Generation ----------

class Claim(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)  # source_ids
    confidence: float = 0.5


class StructuredAnswer(BaseModel):
    answer_summary: str
    claims: list[Claim] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
