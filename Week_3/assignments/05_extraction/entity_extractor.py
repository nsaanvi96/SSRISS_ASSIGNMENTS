#!/usr/bin/env python3
"""entity_extractor.py - Explicit Entity Extraction for Event Records (Assignment 5)

Extracts structured people and organization entities strictly from explicit
field markers (e.g., "Speaker:", "Organized by:", "Chair:").

Core Rules Enforced
-------------------
1. Extract ONLY what the source text explicitly supports.
2. Preserve raw text (names, titles, raw affiliations).
3. Do NOT infer political orientation or ideology.
4. Do NOT infer affiliations not explicitly shown in the field/line.
5. Do NOT merge two people solely because their names look similar.
6. Provenance: Every extracted entity retains a `source_text` pointer
   referencing the exact line that produced it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ExtractedPerson:
    """A person entity extracted from explicit event fields."""
    name:            str
    role:            str
    affiliation_raw: Optional[str]
    source_text:     str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":            self.name,
            "role":            self.role,
            "affiliation_raw": self.affiliation_raw,
            "source_text":     self.source_text,
        }


@dataclass
class ExtractedOrganization:
    """An organization entity extracted from explicit event fields."""
    name:        str
    role:        str
    source_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":        self.name,
            "role":        self.role,
            "source_text": self.source_text,
        }


@dataclass
class EventEntities:
    """Container for all entities extracted from an event record."""
    people:        List[ExtractedPerson] = field(default_factory=list)
    organizations: List[ExtractedOrganization] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "people":        [p.to_dict() for p in self.people],
            "organizations": [o.to_dict() for o in self.organizations],
        }


# ---------------------------------------------------------------------------
# Explicit Field Matchers and Role Definitions
# ---------------------------------------------------------------------------

# Patterns for people roles: (regex pattern, canonical role name)
PEOPLE_FIELD_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:Keynote\s+Speaker|Guest\s+Speaker|Invited\s+Speaker)\s*:\s*(.+)$", re.IGNORECASE), "speaker"),
    (re.compile(r"^(?:Speaker|Speakers)\s*:\s*(.+)$", re.IGNORECASE), "speaker"),
    (re.compile(r"^(?:Session\s+Chair|Chair|Chairs)\s*:\s*(.+)$", re.IGNORECASE), "chair"),
    (re.compile(r"^(?:Co-chair|Co-Chair)\s*:\s*(.+)$", re.IGNORECASE), "co_chair"),
    (re.compile(r"^(?:Moderator|Moderators)\s*:\s*(.+)$", re.IGNORECASE), "moderator"),
    (re.compile(r"^(?:Panelist|Panelists)\s*:\s*(.+)$", re.IGNORECASE), "panelist"),
    (re.compile(r"^(?:Discussant|Discussants)\s*:\s*(.+)$", re.IGNORECASE), "discussant"),
    (re.compile(r"^(?:Presenter|Presenters)\s*:\s*(.+)$", re.IGNORECASE), "presenter"),
    (re.compile(r"^(?:Chief\s+Guest)\s*:\s*(.+)$", re.IGNORECASE), "chief_guest"),
    (re.compile(r"^(?:Instructor|Instructors)\s*:\s*(.+)$", re.IGNORECASE), "instructor"),
    (re.compile(r"^(?:Coordinator|Coordinators)\s*:\s*(.+)$", re.IGNORECASE), "coordinator"),
    (re.compile(r"^(?:Advisor|Advisors)\s*:\s*(.+)$", re.IGNORECASE), "advisor"),
    (re.compile(r"^(?:Co-advisor|Co-Advisor)\s*:\s*(.+)$", re.IGNORECASE), "co_advisor"),
    (re.compile(r"^(?:Welcome\s+Address)\s*:\s*(.+)$", re.IGNORECASE), "welcome_address"),
    (re.compile(r"^(?:Vote\s+of\s+Thanks)\s*:\s*(.+)$", re.IGNORECASE), "vote_of_thanks"),
]

# Patterns for organization roles: (regex pattern, canonical role name)
ORG_FIELD_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:Organized\s+by|Organisers?|Organizers?)\s*:\s*(.+)$", re.IGNORECASE), "organizer"),
    (re.compile(r"^(?:Co-organized\s+by|Co-organisers?|Co-organizers?)\s*:\s*(.+)$", re.IGNORECASE), "co_organizer"),
    (re.compile(r"^(?:In\s+collaboration\s+with|Collaboration|Partner)\s*:\s*(.+)$", re.IGNORECASE), "collaborator"),
    (re.compile(r"^(?:Hosted\s+by|Host)\s*:\s*(.+)$", re.IGNORECASE), "host"),
    (re.compile(r"^(?:Presented\s+by)\s*:\s*(.+)$", re.IGNORECASE), "presenter"),
]


# ---------------------------------------------------------------------------
# Person Substring Parser (Splits Name & Affiliation)
# ---------------------------------------------------------------------------

def parse_person_entry(raw_entry: str) -> Tuple[str, Optional[str]]:
    """Parse a single person entry into (name, affiliation_raw).
    
    Preserves raw casing and text. Does NOT infer any missing affiliation.
    
    Examples:
        "Dr. Example, Centre for Example Studies"
            -> ("Dr. Example", "Centre for Example Studies")
        "Prof. Sample"
            -> ("Prof. Sample", None)
        "Dr. Elena Rostova (Institute for Advanced Study, Princeton)"
            -> ("Dr. Elena Rostova", "Institute for Advanced Study, Princeton")
        "Prof. Amit Sen - Centre for Policy Research"
            -> ("Prof. Amit Sen", "Centre for Policy Research")
    """
    entry = raw_entry.strip()
    if not entry:
        return "", None

    # Pattern 1: Parentheses -> Name (Affiliation)
    paren_match = re.match(r"^([^(]+?)\s*\(([^)]+)\)$", entry)
    if paren_match:
        name = paren_match.group(1).strip()
        affil = paren_match.group(2).strip()
        return name, (affil if affil else None)

    # Pattern 2: Hyphen separator -> Name - Affiliation
    # Ensure hyphen is surrounded by spaces so we don't break hyphenated names
    if " - " in entry:
        parts = entry.split(" - ", 1)
        name = parts[0].strip()
        affil = parts[1].strip()
        return name, (affil if affil else None)

    # Pattern 3: Comma separator -> Name, Affiliation
    # When multiple commas exist (e.g. "Dr. Robert Lang, Department of Economics, Harvard University"),
    # the first comma splits the person name from the remaining institutional hierarchy.
    if "," in entry:
        parts = entry.split(",", 1)
        name = parts[0].strip()
        affil = parts[1].strip()
        return name, (affil if affil else None)

    # Pattern 4: Standalone name with no affiliation given
    return entry, None


# ---------------------------------------------------------------------------
# Core Extractor
# ---------------------------------------------------------------------------

class EntityExtractor:
    """Extracts explicit people and organization entities from text or record dicts."""

    def extract_from_text(self, text: str) -> EventEntities:
        """Extract entities line-by-line from a text block.
        
        Guarantees:
        - Strict adherence to explicit markers.
        - Provenance preserved via `source_text`.
        - No cross-entity merging based on name similarity.
        - No political inference.
        """
        entities = EventEntities()
        if not text:
            return entities

        lines = text.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # 1. Check for Organization field markers
            matched_org = False
            for pattern, role in ORG_FIELD_PATTERNS:
                m = pattern.match(line_str)
                if m:
                    org_val = m.group(1).strip()
                    # Organizations may be semicolon-delimited if multiple
                    org_names = [o.strip() for o in org_val.split(";") if o.strip()]
                    for name in org_names:
                        entities.organizations.append(
                            ExtractedOrganization(
                                name=name,
                                role=role,
                                source_text=line_str,
                            )
                        )
                    matched_org = True
                    break

            if matched_org:
                continue

            # 2. Check for People field markers
            for pattern, role in PEOPLE_FIELD_PATTERNS:
                m = pattern.match(line_str)
                if m:
                    people_val = m.group(1).strip()
                    # If multiple people on one line, they are separated by semicolon ';'
                    # (Comma is preserved for "Name, Affiliation")
                    if ";" in people_val:
                        raw_entries = [e.strip() for e in people_val.split(";") if e.strip()]
                    else:
                        raw_entries = [people_val]

                    for raw_entry in raw_entries:
                        name, affil = parse_person_entry(raw_entry)
                        if name:
                            entities.people.append(
                                ExtractedPerson(
                                    name=name,
                                    role=role,
                                    affiliation_raw=affil,
                                    source_text=line_str,
                                )
                            )
                    break

        return entities

    def extract_from_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from a record dictionary.
        
        Looks in 'raw_text', 'description', and 'title'.
        Returns the canonical entity dict structure:
        {
            "people": [...],
            "organizations": [...]
        }
        """
        # Combine candidate text fields in order of specificity
        text_sources = []
        if record.get("raw_text"):
            text_sources.append(record["raw_text"])
        if record.get("description"):
            text_sources.append(record["description"])

        combined_text = "\n".join(text_sources)
        extracted = self.extract_from_text(combined_text)
        return extracted.to_dict()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def extract_entities(text_or_record: str | Dict[str, Any]) -> Dict[str, Any]:
    """Top-level convenience interface for Assignment 5 entity extraction."""
    extractor = EntityExtractor()
    if isinstance(text_or_record, str):
        return extractor.extract_from_text(text_or_record).to_dict()
    return extractor.extract_from_record(text_or_record)


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    sample_input = """Speaker: Dr. Example, Centre for Example Studies
Organized by: Department of Example
Chair: Prof. Sample"""

    print("=" * 60)
    print("SOURCE TEXT:")
    print(sample_input)
    print("=" * 60)
    print("EXTRACTED STRUCTURE:")
    result = extract_entities(sample_input)
    print(json.dumps(result, indent=2))
