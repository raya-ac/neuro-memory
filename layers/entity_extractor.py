#!/usr/bin/env python3
"""
Entity Extractor - Automatic NER and relationship extraction
Pattern-based (no ML) for speed and simplicity
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger("neuro-memory.entities")


@dataclass
class Entity:
    """Extracted entity"""
    name: str
    type: str  # person, project, technology, date, url, email, concept
    canonical: str  # normalized form
    confidence: float  # 0-1
    context: str  # surrounding text snippet


@dataclass
class Relationship:
    """Extracted relationship between entities"""
    source: str  # canonical name
    target: str  # canonical name
    type: str  # WORKS_WITH, USES, MENTIONS, etc.
    confidence: float
    evidence: str  # text that suggested this relationship


class EntityExtractor:
    """Pattern-based entity and relationship extraction"""

    # Patterns for different entity types
    PATTERNS = {
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'url': re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'),
        'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        'date_iso': re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
        'date_us': re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
        'time': re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b', re.I),
        'money': re.compile(r'\$\d+(?:,\d{3})*(?:\.\d{2})?'),
        'percent': re.compile(r'\d+(?:\.\d+)?%'),
        'version': re.compile(r'\bv?\d+\.\d+(?:\.\d+)?\b'),
        'camel_case': re.compile(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b'),  # CamelCase
        'all_caps': re.compile(r'\b[A-Z]{2,}(?:_[A-Z]+)*\b'),  # ALL_CAPS or CONSTANT_NAMES
        'file_path': re.compile(r'(?:/[\w.-]+)+|\b[\w.-]+\.[a-zA-Z]{2,4}\b'),
    }

    # Person name patterns
    PERSON_PATTERNS = [
        re.compile(r'\b([A-Z][a-z]+)\s+(?:said|told|asked|replied|mentioned|noted)\b'),
        re.compile(r'\bmet\s+(?:with\s+)?([A-Z][a-z]+)\b'),
        re.compile(r'\b([A-Z][a-z]+)\s+(?:works|worked|is|was)\s+(?:with|on|at)\b'),
        re.compile(r'\b(?:called|emailed|texted)\s+([A-Z][a-z]+)\b'),
        re.compile(r'\b([A-Z][a-z]+)\s+(?:and|&)\s+([A-Z][a-z]+)\b'),
        re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\'s\b'),  # possessive
    ]

    # Technology patterns
    TECH_PATTERNS = [
        re.compile(r'\b(Python|JavaScript|TypeScript|Java|Go|Rust|C\+\+|Ruby|PHP|Swift|Kotlin)\b'),
        re.compile(r'\b(React|Vue|Angular|Django|Flask|FastAPI|Express|Rails)\b'),
        re.compile(r'\b(Docker|Kubernetes|Redis|PostgreSQL|MongoDB|Neo4j|SQLite)\b'),
        re.compile(r'\b(AWS|GCP|Azure|Lambda|EC2|S3)\b'),
        re.compile(r'\b(API|REST|GraphQL|gRPC|WebSocket)\b'),
    ]

    # Relationship patterns
    RELATIONSHIP_PATTERNS = [
        (re.compile(r'\b([A-Z][a-z]+)\s+works\s+with\s+([A-Z][a-z]+)\b', re.I), 'WORKS_WITH'),
        (re.compile(r'\b([A-Z][a-z]+)\s+(?:is|are)\s+(?:working|working\s+on)\s+([A-Z][a-zA-Z\s]+)\b', re.I), 'WORKS_ON'),
        (re.compile(r'\b([A-Z][a-zA-Z\s]+)\s+(?:uses?|built\s+with)\s+([A-Z][a-z]+)\b', re.I), 'USES'),
        (re.compile(r'\b([A-Z][a-z]+)\s+(?:manages?|leads?|owns?)\s+([A-Z][a-zA-Z\s]+)\b', re.I), 'MANAGES'),
        (re.compile(r'\b([A-Z][a-zA-Z\s]+)\s+(?:depends?\s+on|requires?)\s+([A-Z][a-zA-Z\s]+)\b', re.I), 'DEPENDS_ON'),
        (re.compile(r'\b([A-Z][a-z]+)\s+(?:mentioned|discussed|talked\s+about)\s+([A-Z][a-zA-Z\s]+)\b', re.I), 'MENTIONS'),
    ]

    def extract_entities(self, text: str) -> List[Entity]:
        """Extract all entities from text"""
        entities = []

        # Pattern-based extraction
        entities.extend(self._extract_pattern_entities(text))

        # Person names
        entities.extend(self._extract_persons(text))

        # Technologies
        entities.extend(self._extract_technologies(text))

        # Projects and concepts (capitalized phrases)
        entities.extend(self._extract_concepts(text))

        # Deduplicate and sort by confidence
        entities = self._deduplicate_entities(entities)
        entities.sort(key=lambda e: e.confidence, reverse=True)

        return entities

    def extract_relationships(self, text: str, entities: List[Entity] = None) -> List[Relationship]:
        """Extract relationships between entities"""
        relationships = []

        # If entities not provided, extract them
        if entities is None:
            entities = self.extract_entities(text)

        entity_names = {e.canonical.lower(): e for e in entities}

        # Pattern-based relationship extraction
        for pattern, rel_type in self.RELATIONSHIP_PATTERNS:
            for match in pattern.finditer(text):
                source = match.group(1).strip()
                target = match.group(2).strip()

                # Verify both are known entities or add them
                source_canonical = self._canonicalize(source)
                target_canonical = self._canonicalize(target)

                relationships.append(Relationship(
                    source=source_canonical,
                    target=target_canonical,
                    type=rel_type,
                    confidence=0.7,
                    evidence=match.group(0)
                ))

        # Co-occurrence based relationships (entities in same sentence)
        relationships.extend(self._extract_cooccurrence(text, entities))

        return relationships

    def _extract_pattern_entities(self, text: str) -> List[Entity]:
        """Extract entities using regex patterns"""
        entities = []

        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                name = match.group(0)
                entities.append(Entity(
                    name=name,
                    type=entity_type,
                    canonical=self._canonicalize(name),
                    confidence=0.9,  # High confidence for pattern matches
                    context=self._get_context(text, match.start(), match.end())
                ))

        return entities

    def _extract_persons(self, text: str) -> List[Entity]:
        """Extract person names using context patterns"""
        entities = []

        for pattern in self.PERSON_PATTERNS:
            for match in pattern.finditer(text):
                # Get all groups that matched
                for i in range(1, len(match.groups()) + 1):
                    name = match.group(i)
                    if name and len(name) > 1:
                        entities.append(Entity(
                            name=name,
                            type='person',
                            canonical=self._canonicalize(name),
                            confidence=0.7,
                            context=self._get_context(text, match.start(), match.end())
                        ))

        return entities

    def _extract_technologies(self, text: str) -> List[Entity]:
        """Extract technology mentions"""
        entities = []

        for pattern in self.TECH_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(0)
                entities.append(Entity(
                    name=name,
                    type='technology',
                    canonical=name.lower(),
                    confidence=0.95,
                    context=self._get_context(text, match.start(), match.end())
                ))

        return entities

    def _extract_concepts(self, text: str) -> List[Entity]:
        """Extract capitalized phrases as concepts/projects"""
        entities = []

        # Multi-word capitalized phrases (likely projects or concepts)
        pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
        for match in pattern.finditer(text):
            name = match.group(1)
            # Skip if it's a person we already found
            if len(name.split()) > 1:  # Multi-word
                entities.append(Entity(
                    name=name,
                    type='concept',
                    canonical=self._canonicalize(name),
                    confidence=0.5,
                    context=self._get_context(text, match.start(), match.end())
                ))

        return entities

    def _extract_cooccurrence(self, text: str, entities: List[Entity]) -> List[Relationship]:
        """Extract relationships based on co-occurrence in sentences"""
        relationships = []

        # Split into sentences
        sentences = re.split(r'[.!?]+', text)

        for sentence in sentences:
            # Find entities in this sentence
            sentence_entities = []
            for entity in entities:
                if entity.name.lower() in sentence.lower():
                    sentence_entities.append(entity)

            # Create MENTIONS relationships between co-occurring entities
            if len(sentence_entities) >= 2:
                for i, e1 in enumerate(sentence_entities):
                    for e2 in sentence_entities[i+1:]:
                        if e1.type != e2.type or e1.type in ['person', 'concept', 'technology']:
                            relationships.append(Relationship(
                                source=e1.canonical,
                                target=e2.canonical,
                                type='CO_OCCURS',
                                confidence=0.4,
                                evidence=sentence[:100]
                            ))

        return relationships

    def _canonicalize(self, name: str) -> str:
        """Convert entity name to canonical form"""
        canonical = name.strip().lower()
        canonical = re.sub(r'[_\s]+', '_', canonical)
        canonical = re.sub(r'[^\w_]', '', canonical)
        return canonical

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get surrounding context for an entity"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities, keeping highest confidence"""
        seen = {}
        for entity in entities:
            key = (entity.canonical, entity.type)
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity
        return list(seen.values())


# Convenience function
def extract(text: str) -> Tuple[List[Entity], List[Relationship]]:
    """Extract entities and relationships from text"""
    extractor = EntityExtractor()
    entities = extractor.extract_entities(text)
    relationships = extractor.extract_relationships(text, entities)
    return entities, relationships


if __name__ == "__main__":
    # Test
    test_text = """
    Alice and Bob are working on Project Phoenix together.
    The project uses Python and React for the frontend.
    Alice mentioned that they're having issues with Redis caching.
    They met with Charlie yesterday to discuss the API design.
    """

    extractor = EntityExtractor()
    entities = extractor.extract_entities(test_text)
    relationships = extractor.extract_relationships(test_text, entities)

    print("Entities:")
    for e in entities:
        print(f"  [{e.type}] {e.name} ({e.confidence:.2f})")

    print("\nRelationships:")
    for r in relationships:
        print(f"  ({r.source})-[:{r.type}]->({r.target})")
