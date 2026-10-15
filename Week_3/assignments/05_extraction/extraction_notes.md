# Assignment 5 — Entity Extraction from Explicit Fields

## Overview

Assignment 5 implements strict, pattern-driven entity extraction from explicit event fields (such as `Speaker:`, `Organized by:`, `Chair:`, `Moderator:`). Rather than using unconstrained NLP or probabilistic guessing, this extractor converts structured and semi-structured text directly into typed `people` and `organizations` records while strictly adhering to extraction provenance and safety rules.

---

## Canonical Output Schema

Given source text such as:

```text
Speaker: Dr. Example, Centre for Example Studies
Organized by: Department of Example
Chair: Prof. Sample
```

The extractor produces:

```json
{
  "people": [
    {
      "name": "Dr. Example",
      "role": "speaker",
      "affiliation_raw": "Centre for Example Studies",
      "source_text": "Speaker: Dr. Example, Centre for Example Studies"
    },
    {
      "name": "Prof. Sample",
      "role": "chair",
      "affiliation_raw": null,
      "source_text": "Chair: Prof. Sample"
    }
  ],
  "organizations": [
    {
      "name": "Department of Example",
      "role": "organizer",
      "source_text": "Organized by: Department of Example"
    }
  ]
}
```

---

## Strict Rules & Enforcement

### 1. Extract only what the page actually supports
- Entities are extracted **only** when explicit field markers appear (e.g. `Speaker:`, `Chair:`, `Organized by:`).
- Narrative sentences that mention people in passing without explicit role indicators are not converted into formal speaker/organizer entities.

### 2. Preserve raw text
- Titles, honorifics, and raw names (`Dr. Example`, `Justice (Retd.) S. Muralidhar`, `Prof. Upendra Baxi`) are preserved verbatim.
- Institutional affiliations (`affiliation_raw`) retain exact strings, commas, and casing (e.g., `"Department of Economics, Harvard University, Cambridge, MA"`).

### 3. Do not infer political orientation
- Even if events address political topics (e.g., *Decolonizing Economic Policy*, *Electoral Trends*, *Constitutional Law*), or feature prominent political/judicial figures, no `political_orientation`, `ideology`, or `party` attribute is inferred or introduced into the entity schema.

### 4. Do not infer affiliations not explicitly shown
- If a line provides only a name (e.g., `Chair: Prof. Sample` or `Chief Guest: Smt. Nirmala Sitharaman`), `affiliation_raw` is set to `None` (`null` in JSON).
- No external knowledge bases or search lookups are used to guess affiliations.

### 5. Do not merge two people solely because their names look similar
- In Event 09:
  - `Dr. Rajesh Kumar, IIT Delhi` (speaker)
  - `Prof. R. Kumar, Jawaharlal Nehru University` (discussant)
  - `Prof. Rajesh Kumar, IIM Bangalore` (chair)
- In Event 13:
  - `Dr. M. K. Patel` (co-chair)
  - `Dr. M. K. Patel Jr., Gujarat Technological University` (chair)
- Each individual is kept as a distinct entity. Phonetic similarity, initial matching, or shared surnames never trigger entity deduplication or loss of distinct records.

---

## Checkpoint: Provenance Linkage

> **Checkpoint**: You should be able to point from every extracted entity back to the source text that produced it.

Every `ExtractedPerson` and `ExtractedOrganization` entity includes a **`source_text`** attribute containing the exact line or text span from the source document that produced it.

In [test_entity_extractor.py](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/test_entity_extractor.py#L65-L101), the test `test_provenance_link_exists_in_all_sample_events` asserts for all 18 fixture events that:
```python
assert person["source_text"] in full_source
assert org["source_text"] in full_source
```
This guarantees an unbroken chain of custody for every extracted entity.

---

## Dataset & Extraction Evaluation

We evaluated the extractor against a fixture dataset of **18 diverse events** ([events_sample.json](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/fixtures/events_sample.json)):

| Event ID | Event Title | Extracted People | Extracted Organizations |
|---|---|---|---|
| `event_01` | Decarbonization Pathways | Dr. Example (`speaker`), Prof. Sample (`chair`) | Department of Example (`organizer`) |
| `event_02` | AMRC 2026 | Prof. Arvind Sharma (`speaker`) | Research and Publications Office, Centre for Management in Agriculture |
| `event_03` | FinTech Frontiers | Prof. R. Ramanathan, Ms. Priya Nair, Dr. Anand Verma, Mr. S. Ramanathan | — |
| `event_04` | Fiscal Federalism | Dr. Tanya Joseph (`speaker`) | School of Public Policy and Governance (`organizer`) |
| `event_05` | Computational Economics | Dr. Elena Rostova (`speaker`, paren affil) | Department of Economics (`host`) |
| `event_06` | Supply Chain Resilience | Prof. Amit Sen (`speaker`, hyphen affil), Prof. Sunita Deshmukh (`chair`) | — |
| `event_07` | Endowment Lecture 2026 | Smt. Nirmala Sitharaman, Prof. Errol D'Souza, Prof. Saral Mukherjee | — |
| `event_08` | Agricultural Credit | Dr. K. Radhakrishnan (`speaker`) | Centre for Management in Agriculture, NABARD |
| `event_09` | AI & Labor Economics | Dr. Rajesh Kumar, Prof. R. Kumar, Prof. Rajesh Kumar *(all distinct)* | — |
| `event_10` | Macroeconomics Workshop | Prof. Arvind Sharma, Dr. Sunita Rao, Mr. Kevin Vance *(multi-speaker line)* | Economics Area (`organizer`) |
| `event_11` | ESG Corporate Finance | Dr. Robert Lang, Prof. Vikram Patel | Centre for ESG Research (`host`) |
| `event_12` | Healthcare Systems | Dr. Meera Nambiar, Dr. Hitesh Shah | Public Health Research Initiative (`presenter`) |
| `event_13` | Digital PDS | Shri Sanjay Kirloskar, Dr. M. K. Patel, Dr. M. K. Patel Jr. | Centre for Digital Transformation (`organizer`) |
| `event_14` | PhD Defense | Ms. Ananya Gupta, Prof. K. V. Subramanian, Prof. Devendra Singh | — |
| `event_15` | Campus Tree Planting | *(None — informal event without formal roles)* | *(None)* |
| `event_16` | Behavioral Game Theory | Prof. Maya Sen, Prof. Amit Sharma | Ravi J. Matthai Centre for Educational Innovation |
| `event_17` | Constitutional Law | Justice (Retd.) S. Muralidhar, Prof. Upendra Baxi | Legal Studies Group, Institute Human Rights Committee |
| `event_18` | Women in Tech | Ms. Kiran Mazumdar-Shaw, Prof. Sneha Roy | CIIE.CO (`organizer`) |
