"""Knowledge graph entity and relationship extraction via LLM.

Extracts structured entities and typed relationships from document
chunks using the configured LLM provider. Results are cached per-chunk
(content hash) so re-indexing unchanged content skips extraction.
"""

import json
import logging
import re

from app.config import Settings
from app.ingestion.parser import Chunk
from app.storage.knowledgegraph import KnowledgeGraphDB, chunk_content_hash

logger = logging.getLogger(__name__)

# Entity types the LLM should extract.
ENTITY_TYPES = [
    "concept", "technology", "tool", "process", "pattern",
    "standard", "organization", "person", "metric", "principle",
]

# Relationship types the LLM should extract.
RELATIONSHIP_TYPES = [
    "uses", "is-a", "part-of", "relates-to", "implements",
    "depends-on", "produces", "defines", "contradicts", "extends",
    "requires", "enables", "measures", "applies-to",
]

_EXTRACTION_PROMPT = """Extract entities and relationships from this text.

Return ONLY a JSON object with this exact structure:
{{
  "entities": [
    {{"name": "entity name", "type": "<type>", "description": "one-line description"}}
  ],
  "relationships": [
    {{"source": "entity name", "target": "entity name", "type": "<rel_type>", "description": "brief description"}}
  ]
}}

Entity types: {entity_types}
Relationship types: {rel_types}

Rules:
- Extract specific, meaningful concepts — not generic words
- Entity names should be concise (1-4 words)
- Only extract relationships between entities you listed
- If there are no clear entities, return empty lists
- Return valid JSON only, no markdown fences

Text:
{text}"""


def _parse_extraction(raw: str) -> dict:
    """Parse LLM output into entities and relationships dict.

    Handles both clean JSON and JSON wrapped in markdown code fences.
    """
    # Try direct JSON parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM extraction output: %.200s", raw)
    return {"entities": [], "relationships": []}


def extract_from_chunks(
    chunks: list[Chunk],
    source_path: str,
    kgdb: KnowledgeGraphDB,
    settings: Settings | None = None,
) -> int:
    """Extract entities and relationships from chunks into the KG.

    Skips chunks that have already been extracted (by content hash).
    Returns the number of entities extracted.
    """
    from app.rag.llm import get_completion

    settings = settings or Settings.get()

    # Filter to chunks that need extraction
    pending = []
    for chunk in chunks:
        ch = chunk_content_hash(chunk.content)
        if not kgdb.is_chunk_extracted(ch):
            pending.append((chunk, ch))

    if not pending:
        return 0

    total_entities = 0

    # Batch chunks (3-4 per LLM call to stay under context limits)
    batch_size = 3
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        combined_text = "\n\n---\n\n".join(c.content for c, _ in batch)

        # Truncate to avoid overwhelming small models
        if len(combined_text) > 6000:
            combined_text = combined_text[:6000]

        prompt = _EXTRACTION_PROMPT.format(
            entity_types=", ".join(ENTITY_TYPES),
            rel_types=", ".join(RELATIONSHIP_TYPES),
            text=combined_text,
        )

        try:
            raw = get_completion(
                messages=[{"role": "user", "content": prompt}],
                settings=settings,
            )
            if not isinstance(raw, str):
                # Stream mode returned — consume it
                raw = "".join(raw)

            result = _parse_extraction(raw)
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            # Upsert entities
            entity_ids: dict[str, int] = {}  # name -> id
            for ent in entities:
                name = ent.get("name", "").strip()
                etype = ent.get("type", "concept").strip().lower()
                desc = ent.get("description", "").strip()
                if not name:
                    continue
                if etype not in ENTITY_TYPES:
                    etype = "concept"

                eid = kgdb.upsert_entity(
                    name=name,
                    entity_type=etype,
                    source_path=source_path,
                    display_name=name,
                    description=desc,
                    chunk_hash=batch[0][1],
                )
                entity_ids[name.strip().lower()] = eid
                total_entities += 1

            # Upsert relationships
            for rel in relationships:
                src_name = (rel.get("source", "") or "").strip().lower()
                tgt_name = (rel.get("target", "") or "").strip().lower()
                rtype = (rel.get("type", "") or "").strip().lower()
                rdesc = (rel.get("description", "") or "").strip()

                if not src_name or not tgt_name or not rtype:
                    continue
                if rtype not in RELATIONSHIP_TYPES:
                    rtype = "relates-to"

                src_id = entity_ids.get(src_name)
                tgt_id = entity_ids.get(tgt_name)
                if src_id and tgt_id:
                    kgdb.upsert_relationship(
                        source_entity_id=src_id,
                        target_entity_id=tgt_id,
                        rel_type=rtype,
                        source_path=source_path,
                        description=rdesc,
                        chunk_hash=batch[0][1],
                    )

        except (RuntimeError, ConnectionError, TimeoutError) as e:
            logger.warning(
                "KG extraction failed for %s (batch %d): %s",
                source_path, i // batch_size, e,
            )
            # Non-fatal — continue with remaining batches

        # Mark chunks as extracted regardless of success
        # (avoids retrying chunks that produce no entities)
        for _, ch in batch:
            kgdb.mark_chunk_extracted(ch, source_path)

    return total_entities
