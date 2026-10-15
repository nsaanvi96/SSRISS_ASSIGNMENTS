#!/usr/bin/env python3
"""test_entity_extractor.py - Tests for Assignment 5: Entity Extraction from Explicit Fields

Run with:   python -m pytest Week_3/assignments/05_extraction/test_entity_extractor.py -v
        or: python Week_3/assignments/05_extraction/test_entity_extractor.py
"""

from __future__ import annotations

import json
import os
import sys

# Allow running from repo root or from inside 05_extraction/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from entity_extractor import (
    EntityExtractor,
    EventEntities,
    ExtractedOrganization,
    ExtractedPerson,
    extract_entities,
    parse_person_entry,
)

_FIXTURE_PATH = os.path.join(_HERE, "fixtures", "events_sample.json")


# ===========================================================================
# 1. Assignment Prompt Baseline Test
# ===========================================================================

class TestPromptCanonicalExample:
    """Verifies the exact example given in the assignment specification."""

    def test_canonical_prompt_example(self):
        source = (
            "Speaker: Dr. Example, Centre for Example Studies\n"
            "Organized by: Department of Example\n"
            "Chair: Prof. Sample"
        )
        result = extract_entities(source)

        assert "people" in result
        assert "organizations" in result

        people = result["people"]
        orgs = result["organizations"]

        assert len(people) == 2
        assert len(orgs) == 1

        # Person 1
        p1 = people[0]
        assert p1["name"] == "Dr. Example"
        assert p1["role"] == "speaker"
        assert p1["affiliation_raw"] == "Centre for Example Studies"
        assert p1["source_text"] == "Speaker: Dr. Example, Centre for Example Studies"

        # Person 2
        p2 = people[1]
        assert p2["name"] == "Prof. Sample"
        assert p2["role"] == "chair"
        assert p2["affiliation_raw"] is None
        assert p2["source_text"] == "Chair: Prof. Sample"

        # Organization 1
        o1 = orgs[0]
        assert o1["name"] == "Department of Example"
        assert o1["role"] == "organizer"
        assert o1["source_text"] == "Organized by: Department of Example"


# ===========================================================================
# 2. Checkpoint Verification: Provenance Linkage
# ===========================================================================

class TestProvenanceCheckpoint:
    """Verifies checkpoint: Every extracted entity MUST point back to source text."""

    def test_provenance_link_exists_in_all_sample_events(self):
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        assert len(records) >= 10, "Expected at least 10–20 event records"

        total_people = 0
        total_orgs = 0

        for rec in records:
            extracted = extract_entities(rec)
            full_source = (rec.get("raw_text", "") + "\n" + rec.get("description", ""))

            for person in extracted["people"]:
                total_people += 1
                source_pointer = person["source_text"]
                assert source_pointer, f"Missing source_text for {person['name']}"
                # Must be an exact substring of the original source text
                assert source_pointer in full_source, (
                    f"Provenance link failed: '{source_pointer}' not found in event {rec['id']}"
                )

            for org in extracted["organizations"]:
                total_orgs += 1
                source_pointer = org["source_text"]
                assert source_pointer, f"Missing source_text for {org['name']}"
                # Must be an exact substring of the original source text
                assert source_pointer in full_source, (
                    f"Provenance link failed: '{source_pointer}' not found in event {rec['id']}"
                )

        assert total_people > 15, f"Expected substantial people extracted, got {total_people}"
        assert total_orgs > 10, f"Expected substantial orgs extracted, got {total_orgs}"


# ===========================================================================
# 3. Rule Compliance Tests
# ===========================================================================

class TestRuleCompliance:
    """Tests the five strict rules defined in the assignment."""

    def test_rule_preserve_raw_text(self):
        """Preserves raw text, casing, honorifics, and commas in affiliation."""
        text = "Speaker: Dr. Robert Lang, Department of Economics, Harvard University, Cambridge, MA"
        result = extract_entities(text)
        person = result["people"][0]

        assert person["name"] == "Dr. Robert Lang"
        assert person["affiliation_raw"] == "Department of Economics, Harvard University, Cambridge, MA"

    def test_rule_no_inferred_affiliations(self):
        """Never infer an affiliation not explicitly stated in the source."""
        text = (
            "Chief Guest: Smt. Nirmala Sitharaman\n"
            "Chair: Prof. Sample"
        )
        result = extract_entities(text)

        for person in result["people"]:
            assert person["affiliation_raw"] is None, (
                f"Affiliation was inferred for {person['name']} despite absence in text"
            )

    def test_rule_do_not_merge_similar_names(self):
        """Do NOT merge two people solely because their names look similar."""
        text = (
            "Speaker: Dr. Rajesh Kumar, IIT Delhi\n"
            "Discussant: Prof. R. Kumar, Jawaharlal Nehru University\n"
            "Chair: Prof. Rajesh Kumar, IIM Bangalore"
        )
        result = extract_entities(text)
        people = result["people"]

        assert len(people) == 3, "Similar names must remain separate extracted entities"
        names = [p["name"] for p in people]
        affils = [p["affiliation_raw"] for p in people]

        assert names == ["Dr. Rajesh Kumar", "Prof. R. Kumar", "Prof. Rajesh Kumar"]
        assert affils == [
            "IIT Delhi",
            "Jawaharlal Nehru University",
            "IIM Bangalore",
        ]

    def test_rule_do_not_merge_junior_suffix(self):
        """Do not merge names with suffixes like Jr. / Sr."""
        text = (
            "Co-chair: Dr. M. K. Patel\n"
            "Chair: Dr. M. K. Patel Jr., Gujarat Technological University"
        )
        result = extract_entities(text)
        assert len(result["people"]) == 2

    def test_rule_no_political_orientation_inferred(self):
        """Never infer or introduce political orientation fields."""
        text = (
            "Topic: Decolonizing Economic Policy and Electoral Trends\n"
            "Keynote Speaker: Justice (Retd.) S. Muralidhar\n"
            "Speaker: Dr. Tanya Joseph, School of Social Sciences"
        )
        result = extract_entities(text)

        # Output schema must only contain people and organizations
        assert set(result.keys()) == {"people", "organizations"}
        for person in result["people"]:
            assert "political_orientation" not in person
            assert "ideology" not in person
            assert "party" not in person


# ===========================================================================
# 4. Parsing and Formatting Variation Tests
# ===========================================================================

class TestParsingVariations:
    """Verifies handling of different delimiters and affiliation formatting styles."""

    def test_parenthetical_affiliation(self):
        name, affil = parse_person_entry("Dr. Elena Rostova (Institute for Advanced Study, Princeton)")
        assert name == "Dr. Elena Rostova"
        assert affil == "Institute for Advanced Study, Princeton"

    def test_hyphen_affiliation(self):
        name, affil = parse_person_entry("Prof. Amit Sen - Centre for Policy Research")
        assert name == "Prof. Amit Sen"
        assert affil == "Centre for Policy Research"

    def test_comma_affiliation(self):
        name, affil = parse_person_entry("Dr. Example, Centre for Example Studies")
        assert name == "Dr. Example"
        assert affil == "Centre for Example Studies"

    def test_standalone_name(self):
        name, affil = parse_person_entry("Prof. Sample")
        assert name == "Prof. Sample"
        assert affil is None

    def test_semicolon_delimited_multiple_people(self):
        text = "Speakers: Prof. Arvind Sharma, IIM Ahmedabad; Dr. Sunita Rao, IISc Bangalore; Mr. Kevin Vance"
        result = extract_entities(text)
        people = result["people"]

        assert len(people) == 3
        assert people[0]["name"] == "Prof. Arvind Sharma"
        assert people[0]["affiliation_raw"] == "IIM Ahmedabad"
        assert people[1]["name"] == "Dr. Sunita Rao"
        assert people[1]["affiliation_raw"] == "IISc Bangalore"
        assert people[2]["name"] == "Mr. Kevin Vance"
        assert people[2]["affiliation_raw"] is None

    def test_multiple_organization_roles(self):
        text = (
            "Organized by: Research and Publications Office\n"
            "Co-organized by: Centre for Management in Agriculture\n"
            "In collaboration with: National Bank for Agriculture and Rural Development\n"
            "Hosted by: Centre for ESG Research"
        )
        result = extract_entities(text)
        orgs = result["organizations"]

        assert len(orgs) == 4
        roles = [o["role"] for o in orgs]
        assert roles == ["organizer", "co_organizer", "collaborator", "host"]

    def test_event_without_entities(self):
        text = (
            "Date: October 25, 2026\n"
            "Venue: Old Campus Quadrangle\n"
            "All students and faculty are invited to join the morning walk."
        )
        result = extract_entities(text)
        assert result["people"] == []
        assert result["organizations"] == []


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestPromptCanonicalExample,
        TestProvenanceCheckpoint,
        TestRuleCompliance,
        TestParsingVariations,
    ]

    passed = failed = 0
    print("=" * 60)
    print("Running Assignment 5 Tests: Entity Extraction from Explicit Fields")
    print("=" * 60)

    for cls in test_classes:
        inst = cls()
        methods = sorted(m for m in dir(inst) if m.startswith("test_"))
        for method in methods:
            try:
                getattr(inst, method)()
                print(f"  PASS  {cls.__name__}.{method}")
                passed += 1
            except Exception:
                print(f"  FAIL  {cls.__name__}.{method}")
                traceback.print_exc()
                failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
