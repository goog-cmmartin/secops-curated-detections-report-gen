# Plan: Curated Detections Agent Skill

## Objective
Enable Gemini CLI to act as a "Curated Detections Agent" by providing tools to search the generated rule database and offering guidance on YARA-L best practices based on curated examples.

## Proposed Components

### 1. New Skill: `secops-curated-rules`
- **Description:** Expert in Google SecOps Curated Detections. Can lookup rules by MITRE Tactic/Technique and provide YARA-L writing guidance.
- **Workflow:**
    - User asks for rules related to a technique (e.g., "Show me rules for T1078").
    - Agent calls `lookup_curated_rules` tool.
    - Agent synthesizes the findings and provides links to the detailed Markdown reports.

### 2. Search Tool: `lookup_curated_rules.py`
- **Capabilities:**
    - Search by `tactic_id` (TAxxxx).
    - Search by `technique_id` (Txxxx).
    - Keyword search in `displayName` and `description`.
    - Filter by `severity` or `precision`.
- **Output:** A concise JSON list of matching rules for the agent to process.

### 3. Knowledge Base: `YARA_L_BEST_PRACTICES.md`
- **Content:**
    - Standard outcome variable naming (e.g., `$risk_score`, `$event_count`).
    - Efficient use of `match` windows.
    - Patterns for multi-event correlation (e.g., Image Replacement pattern).
    - Using `metrics` for UEBA-style rules.

## Implementation Steps

1.  **Draft `lookup_curated_rules.py`:** A standalone script that queries `chronicle_rulesets_with_rules.jsonl`.
2.  **Draft `YARA_L_BEST_PRACTICES.md`:** Distill patterns from the 100+ curated rules.
3.  **Define the Skill:** Call `skill-creator` or manually write the `SKILL.md` structure.
4.  **Verification:** Test the lookup script with various MITRE IDs.

## Verification & Testing
- Run `python lookup_curated_rules.py --technique T1078` and verify output.
- Ask Gemini CLI (with the skill activated): "How do curated rules typically handle risk scoring?" and verify it uses the best practices doc.
