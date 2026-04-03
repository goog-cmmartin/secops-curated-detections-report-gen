---
name: secops-curated-detection-rules
description: Expert on Google SecOps Curated Detections. Use when searching for curated rules, detection patterns, MITRE tactics/techniques, or YARA-L best practices within Google SecOps.
---
# Curated Detections Agent

This skill enables Gemini CLI to act as an expert on Google SecOps Curated Detections. It provides tools to search through local rule data and offers best-practice guidance for writing YARA-L rules.

## Instructions

### 1. Rule Lookup
When a user asks for curated rules, detection patterns, or examples related to a specific MITRE Tactic, Technique, or keyword:
1. Use the `scripts/lookup_curated_rules.py` script to search the local database.
   - Default DB Path: `references/chronicle_rulesets_with_rules.jsonl`
2. Provide a summary of the matching rules, including their names, descriptions, and severity.
3. Reference the detailed Markdown reports in `references/chronicle_rulesets_md_files/` for the full YARA-L code.

### 2. Full Documentation & Code
If a user asks for the full documentation, the YARA-L code, or "more detail" on a specific rule:
1. Identify the `documentationPath` from the `lookup_curated_rules.py` output. (Note: the path is relative to the project root).
2. Read the file at that path using standard file-reading capabilities.
3. Provide the content of the Markdown report, which contains the visual severity badges, MITRE links, and collapsible rule text.

### 3. YARA-L Best Practices
When a user asks for help writing YARA-L rules or requests feedback on a rule draft:
1. Refer to the `YARA_L_BEST_PRACTICES.md` file for established patterns.
2. Use the curated rules as "Gold Standard" examples to recommend improvements (e.g., standard outcome variables, risk scoring logic, or efficient match windows).

## Available Tools

### `scripts/lookup_curated_rules.py`
Searches the `references/chronicle_rulesets_with_rules.jsonl` database for matching rules.

**Parameters:**
- `tactic` (string): MITRE Tactic ID (e.g., "TA0005").
- `technique` (string): MITRE Technique ID (e.g., "T1078").
- `keyword` (string): Keyword to search in name or description.
- `limit` (number): Maximum number of results to return (default: 10).

## Available Resources
- `references/chronicle_rulesets_with_rules.jsonl`: (Generated) The primary database of all curated rules.
- `references/chronicle_rulesets_md_files/`: (Generated) Directory containing detailed human-readable reports.
- `YARA_L_BEST_PRACTICES.md`: A guide to writing high-quality YARA-L rules.
