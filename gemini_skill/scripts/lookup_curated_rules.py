#!/usr/bin/env python3
import json
import argparse
import sys
import os

def get_markdown_filename(display_name, rule_set_id):
    """Replicates the sanitization logic from the generator script."""
    sanitized = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in display_name).strip()
    sanitized = "_".join(sanitized.split())
    return f"{sanitized}_{rule_set_id}.md"

def lookup_rules(db_path, tactic=None, technique=None, keyword=None, search_code=False):
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found.", file=sys.stderr)
        return []

    results = []
    with open(db_path, 'r', encoding='utf-8') as f:
        for line in f:
            rule_set = json.loads(line)
            rs_display_name = rule_set.get('ruleSetDisplayName', 'Untitled')
            rs_id = rule_set.get('ruleSetId', 'N/A')
            md_filename = get_markdown_filename(rs_display_name, rs_id)
            
            for rule in rule_set.get('rules', []):
                match = True
                
                if tactic:
                    tactic_match = any(t.get('id') == tactic for t in rule.get('tactics', []))
                    if not tactic_match: match = False
                
                if technique and match:
                    tech_match = any(t.get('id') == technique or t.get('id', '').startswith(technique + '.') for t in rule.get('techniques', []))
                    if not tech_match: match = False
                
                if keyword and match:
                    k = keyword.lower()
                    # Search name and description
                    in_metadata = (k in rule.get('ruleDisplayName', '').lower() or 
                                  k in rule.get('ruleDescription', '').lower())
                    
                    # Optionally search the actual YARA-L code
                    in_code = False
                    if search_code:
                        in_code = k in rule.get('ruleText', '').lower()
                    
                    if not (in_metadata or in_code):
                        match = False
                
                if match:
                    # Enrich with RuleSet info and documentation path
                    rule['ruleSetName'] = rs_display_name
                    rule['ruleSetId'] = rs_id
                    rule['documentationPath'] = f"gemini_skill/references/chronicle_rulesets_md_files/{md_filename}"
                    
                    # CONTEXT OPTIMIZATION:
                    # We remove the full ruleText from the search results to save tokens.
                    # The agent is instructed to use the 'documentationPath' to get the full code.
                    rule.pop('ruleText', None)
                    
                    results.append(rule)
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Lookup Curated Detections")
    parser.add_argument("--db", default="gemini_skill/references/chronicle_rulesets_with_rules.jsonl", help="Path to JSONL database")
    parser.add_argument("--tactic", help="MITRE Tactic ID (e.g. TA0005)")
    parser.add_argument("--technique", help="MITRE Technique ID (e.g. T1078)")
    parser.add_argument("--keyword", help="Keyword search in name/description (and code if --search-code is set)")
    parser.add_argument("--search-code", action="store_true", help="Include the YARA-L rule text in the keyword search")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    
    args = parser.parse_args()
    
    matches = lookup_rules(args.db, args.tactic, args.technique, args.keyword, args.search_code)
    
    # Sort by display name and limit
    matches.sort(key=lambda x: x.get('ruleDisplayName', ''))
    output = matches[:args.limit]
    
    # Print as JSON for the agent to consume
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
