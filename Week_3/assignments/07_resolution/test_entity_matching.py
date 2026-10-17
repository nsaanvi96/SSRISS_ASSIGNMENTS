#!/usr/bin/env python3
"""test_entity_matching.py - Tests for Assignment 7: Entity Matching Exercise

Run with:   python -m pytest Week_3/assignments/07_resolution/test_entity_matching.py -v
        or: python Week_3/assignments/07_resolution/test_entity_matching.py
"""

from __future__ import annotations

import json
import os
import sys

# Allow running from repo root or from inside 07_resolution/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from entity_matcher import (
    MatchDecision,
    classify_organization_match,
    classify_person_match,
    evaluate_pair,
)

_FIXTURE_PATH = os.path.join(_HERE, "fixtures", "matching_pairs.json")


# ===========================================================================
# 1. Full Fixture Evaluation Test
# ===========================================================================

class TestFixturePairDecisions:
    """Evaluates all 18 test pairs in matching_pairs.json against the policy engine."""

    def test_all_18_fixture_pairs(self):
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            pairs = json.load(f)

        assert len(pairs) == 18, "Expected 18 pairs in fixture"

        for p in pairs:
            result = evaluate_pair(p)
            assert result.decision.value == p["expected_decision"], (
                f"Mismatch for pair {p['id']} ('{p['entity_a']}' vs '{p['entity_b']}'):\n"
                f"  Got:      {result.decision.value}\n"
                f"  Expected: {p['expected_decision']}\n"
                f"  Reason:   {result.rationale}"
            )


# ===========================================================================
# 2. Checkpoint Verification: Weak Similarity Never Authoritative
# ===========================================================================

class TestCheckpointWeakSimilarity:
    """Verifies checkpoint: Your code should not turn a weak similarity score
    into an authoritative identity claim."""

    def test_initial_first_name_is_never_safe_auto_match(self):
        """'A. Rao' vs 'Ananya Rao' must NEVER be safe automatic match."""
        res = classify_person_match("A. Rao", "Ananya Rao")
        assert res.decision != MatchDecision.SAFE_AUTOMATIC_MATCH
        assert res.decision == MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW

    def test_initial_surname_is_never_safe_auto_match(self):
        """'Ananya R.' vs 'Ananya Rao' must NEVER be safe automatic match."""
        res = classify_person_match("Ananya R.", "Ananya Rao")
        assert res.decision != MatchDecision.SAFE_AUTOMATIC_MATCH
        assert res.decision == MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW

    def test_double_truncation_is_never_auto_match(self):
        """'A. Rao' vs 'Ananya R.' must NOT even be possible match (too ambiguous)."""
        res = classify_person_match("A. Rao", "Ananya R.")
        assert res.decision == MatchDecision.DO_NOT_MATCH_AUTOMATICALLY

    def test_standalone_acronym_is_never_safe_auto_match(self):
        """'CPR' vs 'Centre for Policy Research' must NEVER be safe automatic match."""
        res = classify_organization_match("CPR", "Centre for Policy Research")
        assert res.decision != MatchDecision.SAFE_AUTOMATIC_MATCH
        assert res.decision == MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW

    def test_short_acronym_iima_is_never_safe_auto_match(self):
        """'IIMA' vs 'Indian Institute of Management Ahmedabad' requires review."""
        res = classify_organization_match("IIMA", "Indian Institute of Management Ahmedabad")
        assert res.decision != MatchDecision.SAFE_AUTOMATIC_MATCH
        assert res.decision == MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW


# ===========================================================================
# 3. Policy Rule Verification: False Split Over False Merge
# ===========================================================================

class TestPolicyRules:
    """Verifies that when identity is uncertain, the policy favors false splits
    (keeping entities separate) over false merges (corrupting data)."""

    def test_common_surname_with_initial_leaves_entities_separate(self):
        """'Dr. Rajesh Kumar' vs 'Prof. R. Kumar' requires review, NOT auto-merged."""
        res = classify_person_match("Dr. Rajesh Kumar", "Prof. R. Kumar")
        assert res.decision == MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW
        # In a database, this flag means two separate rows are maintained!

    def test_same_first_name_different_surname_strictly_rejected(self):
        """'Ananya Rao' vs 'Ananya Sharma' must be DO_NOT_MATCH_AUTOMATICALLY."""
        res = classify_person_match("Ananya Rao", "Ananya Sharma")
        assert res.decision == MatchDecision.DO_NOT_MATCH_AUTOMATICALLY

    def test_same_surname_different_first_name_strictly_rejected(self):
        """'Arvind Sharma' vs 'Amit Sharma' must be DO_NOT_MATCH_AUTOMATICALLY."""
        res = classify_person_match("Arvind Sharma", "Amit Sharma")
        assert res.decision == MatchDecision.DO_NOT_MATCH_AUTOMATICALLY

    def test_differing_department_disciplines_rejected(self):
        """'School of Public Policy' vs 'School of Public Health' must be DO_NOT_MATCH."""
        res = classify_organization_match("School of Public Policy", "School of Public Health")
        assert res.decision == MatchDecision.DO_NOT_MATCH_AUTOMATICALLY


# ===========================================================================
# 4. Safe Automatic Match Invariants
# ===========================================================================

class TestSafeAutomaticMatches:
    """Verifies cases where automatic merging is provably safe."""

    def test_honorific_variance_is_safe(self):
        res = classify_person_match("Prof. Ananya Rao", "Ananya Rao")
        assert res.decision == MatchDecision.SAFE_AUTOMATIC_MATCH

    def test_punctuation_variance_is_safe(self):
        res = classify_person_match("Prof. Ananya Rao", "Prof Ananya Rao")
        assert res.decision == MatchDecision.SAFE_AUTOMATIC_MATCH

    def test_british_american_spelling_is_safe(self):
        res = classify_organization_match("Centre for Policy Research", "Center for Policy Research")
        assert res.decision == MatchDecision.SAFE_AUTOMATIC_MATCH

    def test_parenthetical_acronym_expansion_is_safe(self):
        res = classify_organization_match(
            "Centre for Policy Research",
            "Centre for Policy Research (CPR)"
        )
        assert res.decision == MatchDecision.SAFE_AUTOMATIC_MATCH

    def test_standard_institution_abbreviation_with_qualifier_is_safe(self):
        res = classify_organization_match(
            "Indian Institute of Management Ahmedabad",
            "IIM Ahmedabad"
        )
        assert res.decision == MatchDecision.SAFE_AUTOMATIC_MATCH


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestFixturePairDecisions,
        TestCheckpointWeakSimilarity,
        TestPolicyRules,
        TestSafeAutomaticMatches,
    ]

    passed = failed = 0
    print("=" * 60)
    print("Running Assignment 7 Tests: Entity Matching Policy")
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
