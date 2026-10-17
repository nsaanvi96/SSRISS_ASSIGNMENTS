#!/usr/bin/env python3
"""entity_matcher.py - Entity Matching Policy & Decision Engine (Assignment 7)

Implements conservative entity resolution policies for People and Organizations.

Core Policy:
- Favor FALSE SPLITS over FALSE MERGES when identity is uncertain.
- Weak or partial similarity produces 'possible match requiring review',
  NEVER 'safe automatic match'.
- Distinct entities produce 'do not match automatically'.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Decision Enum
# ---------------------------------------------------------------------------

class MatchDecision(str, Enum):
    SAFE_AUTOMATIC_MATCH             = "safe automatic match"
    POSSIBLE_MATCH_REQUIRING_REVIEW  = "possible match requiring review"
    DO_NOT_MATCH_AUTOMATICALLY       = "do not match automatically"


@dataclass
class MatchResult:
    entity_type: str
    entity_a:    str
    entity_b:    str
    decision:    MatchDecision
    rationale:   str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_a":    self.entity_a,
            "entity_b":    self.entity_b,
            "decision":    self.decision.value,
            "rationale":   self.rationale,
        }


# ---------------------------------------------------------------------------
# Normalization Utilities
# ---------------------------------------------------------------------------

_HONORIFIC_REGEX = re.compile(
    r"^(?:prof(?:essor)?|dr|mr|ms|mrs|smt|shri|justice|adv(?:ocate)?)\.?\s+",
    re.IGNORECASE,
)

def _normalize_person(name: str) -> str:
    """Strip honorifics, punctuation, and lowercase person name."""
    clean = name.strip().lower()
    clean = _HONORIFIC_REGEX.sub("", clean).strip()
    # Remove dots and extraneous punctuation
    clean = re.sub(r"[\.,]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _normalize_org(org: str) -> Tuple[str, Optional[str]]:
    """Normalize organization name, standardizing British/American spelling
    and separating any trailing parenthetical acronym.
    
    Returns: (normalized_name, extracted_acronym)
    """
    clean = org.strip().lower()
    extracted_acronym = None

    # Extract parenthetical acronym if present, e.g. "Centre for Policy Research (CPR)"
    paren_match = re.search(r"\(([^)]+)\)$", clean)
    if paren_match:
        inner = paren_match.group(1).strip()
        if len(inner) <= 6 and inner.isalpha():
            extracted_acronym = inner
            clean = clean[:paren_match.start()].strip()

    # Standardize British vs American spelling
    clean = re.sub(r"\bcentre\b", "center", clean)

    # Standardize known institutional phrases
    clean = re.sub(r"\bindian institute of management\b", "iim", clean)

    # Clean whitespace and punctuation
    clean = re.sub(r"[,\.]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean, extracted_acronym


def _get_acronym(words: List[str]) -> str:
    """Generate acronym from a list of words, skipping minor stopwords."""
    stopwords = {"for", "of", "in", "and", "the", "to", "on"}
    return "".join(w[0] for w in words if w and w not in stopwords)


# ---------------------------------------------------------------------------
# Match Classifiers
# ---------------------------------------------------------------------------

def classify_person_match(name_a: str, name_b: str) -> MatchResult:
    """Decide match classification between two person name strings.
    
    Policy:
    1. Exact normalized match -> SAFE_AUTOMATIC_MATCH
    2. Initial vs full name expansion -> POSSIBLE_MATCH_REQUIRING_REVIEW
       (initial creates ambiguity; cannot safely auto-merge)
    3. Conflicting full names or conflicting surnames -> DO_NOT_MATCH_AUTOMATICALLY
    4. Truncated on both sides (e.g. A. Rao vs Ananya R.) -> DO_NOT_MATCH_AUTOMATICALLY
    """
    norm_a = _normalize_person(name_a)
    norm_b = _normalize_person(name_b)

    # 1. Exact match after normalization (honorifics/punctuation stripped)
    if norm_a == norm_b:
        return MatchResult(
            entity_type="person",
            entity_a=name_a,
            entity_b=name_b,
            decision=MatchDecision.SAFE_AUTOMATIC_MATCH,
            rationale="Identical normalized full name after stripping honorifics and punctuation.",
        )

    parts_a = norm_a.split()
    parts_b = norm_b.split()

    if len(parts_a) >= 2 and len(parts_b) >= 2:
        first_a, last_a = parts_a[0], parts_a[-1]
        first_b, last_b = parts_b[0], parts_b[-1]

        is_init_first_a = len(first_a) == 1
        is_init_first_b = len(first_b) == 1
        is_init_last_a  = len(last_a) == 1
        is_init_last_b  = len(last_b) == 1

        # Case: Double truncation (A. Rao vs Ananya R.)
        if (is_init_first_a or is_init_first_b) and (is_init_last_a or is_init_last_b):
            return MatchResult(
                entity_type="person",
                entity_a=name_a,
                entity_b=name_b,
                decision=MatchDecision.DO_NOT_MATCH_AUTOMATICALLY,
                rationale="Both entities have truncated components. Insufficient mutual information.",
            )

        # Case: Surnames match, one first name is an initial matching the other's start
        if last_a == last_b and not is_init_last_a and not is_init_last_b:
            if (is_init_first_a and first_b.startswith(first_a)) or \
               (is_init_first_b and first_a.startswith(first_b)):
                return MatchResult(
                    entity_type="person",
                    entity_a=name_a,
                    entity_b=name_b,
                    decision=MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW,
                    rationale="Initial-only first name matches first letter of full name; risk of person collision requires contextual review.",
                )

        # Case: First names match, one surname is an initial matching the other's start
        if first_a == first_b and not is_init_first_a and not is_init_first_b:
            if (is_init_last_a and last_b.startswith(last_a)) or \
               (is_init_last_b and last_a.startswith(last_b)):
                return MatchResult(
                    entity_type="person",
                    entity_a=name_a,
                    entity_b=name_b,
                    decision=MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW,
                    rationale="Initial-only surname matches first letter of full surname; ambiguous identity requires review.",
                )

        # Case: Disjoint surnames or disjoint first names
        if last_a != last_b and not is_init_last_a and not is_init_last_b:
            return MatchResult(
                entity_type="person",
                entity_a=name_a,
                entity_b=name_b,
                decision=MatchDecision.DO_NOT_MATCH_AUTOMATICALLY,
                rationale="Surnames are completely distinct. Definite non-match.",
            )

        if first_a != first_b and not is_init_first_a and not is_init_first_b:
            return MatchResult(
                entity_type="person",
                entity_a=name_a,
                entity_b=name_b,
                decision=MatchDecision.DO_NOT_MATCH_AUTOMATICALLY,
                rationale="Full first names are distinct. Definite non-match.",
            )

    # Fallback default for any non-matching names
    return MatchResult(
        entity_type="person",
        entity_a=name_a,
        entity_b=name_b,
        decision=MatchDecision.DO_NOT_MATCH_AUTOMATICALLY,
        rationale="Names differ without satisfying candidate similarity rules.",
    )


def classify_organization_match(org_a: str, org_b: str) -> MatchResult:
    """Decide match classification between two organization strings.
    
    Policy:
    1. Exact normalized match (including spelling & parenthetical acronym strip) -> SAFE_AUTOMATIC_MATCH
    2. Acronym vs full organization name -> POSSIBLE_MATCH_REQUIRING_REVIEW
       (acronyms frequently collide across domains; require human/context review)
    3. Distinct organizations -> DO_NOT_MATCH_AUTOMATICALLY
    """
    clean_a, acr_a = _normalize_org(org_a)
    clean_b, acr_b = _normalize_org(org_b)

    # 1. Exact match after spelling equivalence and parenthetical acronym stripping
    if clean_a == clean_b:
        return MatchResult(
            entity_type="organization",
            entity_a=org_a,
            entity_b=org_b,
            decision=MatchDecision.SAFE_AUTOMATIC_MATCH,
            rationale="Organizations match after British/American spelling harmonization and parenthetical expansion.",
        )

    # 2. Check acronym relationships
    tokens_a = clean_a.split()
    tokens_b = clean_b.split()

    raw_tokens_a = re.findall(r"\b[a-zA-Z]+\b", org_a.lower())
    raw_tokens_b = re.findall(r"\b[a-zA-Z]+\b", org_b.lower())

    derived_acronyms_a = {_get_acronym(tokens_a), _get_acronym(raw_tokens_a), acr_a}
    derived_acronyms_b = {_get_acronym(tokens_b), _get_acronym(raw_tokens_b), acr_b}
    # Also add standard concatenation of initials
    derived_acronyms_a.add("".join(w[0] for w in raw_tokens_a))
    derived_acronyms_b.add("".join(w[0] for w in raw_tokens_b))
    derived_acronyms_a.discard(None)
    derived_acronyms_b.discard(None)

    raw_a_clean = re.sub(r"[^a-zA-Z]", "", org_a).lower()
    raw_b_clean = re.sub(r"[^a-zA-Z]", "", org_b).lower()

    # Is one side a standalone acronym of the other?
    is_acronym_match = False
    if len(tokens_a) == 1 and (tokens_a[0] in derived_acronyms_b or tokens_a[0] == raw_b_clean):
        is_acronym_match = True
    elif len(tokens_b) == 1 and (tokens_b[0] in derived_acronyms_a or tokens_b[0] == raw_a_clean):
        is_acronym_match = True

    if is_acronym_match:
        return MatchResult(
            entity_type="organization",
            entity_a=org_a,
            entity_b=org_b,
            decision=MatchDecision.POSSIBLE_MATCH_REQUIRING_REVIEW,
            rationale="Acronym matches full name initials, but standalone acronyms carry domain collision risk. Review required.",
        )

    # 3. Disjoint organizations
    return MatchResult(
        entity_type="organization",
        entity_a=org_a,
        entity_b=org_b,
        decision=MatchDecision.DO_NOT_MATCH_AUTOMATICALLY,
        rationale="Distinct organizational entities with non-matching core keywords.",
    )


def evaluate_pair(pair_dict: Dict[str, Any]) -> MatchResult:
    """Evaluate a single pair dictionary matching the fixture schema."""
    e_type = pair_dict.get("entity_type", "person")
    a = pair_dict["entity_a"]
    b = pair_dict["entity_b"]
    if e_type == "organization":
        return classify_organization_match(a, b)
    return classify_person_match(a, b)


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    fixture_path = os.path.join(_HERE, "fixtures", "matching_pairs.json")

    with open(fixture_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    print("=" * 75)
    print("ASSIGNMENT 7 — ENTITY MATCHING POLICY EVALUATION")
    print("=" * 75)

    all_matched = True
    for p in pairs:
        res = evaluate_pair(p)
        expected = p["expected_decision"]
        is_ok = (res.decision.value == expected)
        mark = "PASS" if is_ok else "FAIL"
        if not is_ok:
            all_matched = False
        print(f"[{mark}] {p['entity_type'].upper():12s} | '{p['entity_a']}' <-> '{p['entity_b']}'")
        print(f"       Decision: {res.decision.value}")
        print(f"       Expected: {expected}")
        print(f"       Rationale: {res.rationale}")
        print("-" * 75)

    print("\nSummary:", "All 18 fixture pairs classified as expected!" if all_matched else "Some discrepancies found.")
