#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Curated Detections Report Generator

Standalone script refactored from a Colab Notebook.
"""

import argparse
import json
import logging
import os
import shutil
import time

import google.auth
from google.auth.transport import requests as google_requests
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Exponential Backoff Configuration ---
MAX_RETRIES = 5             # Maximum number of times to retry a failed request
INITIAL_BACKOFF_DELAY = 1   # Initial delay in seconds before first retry
MAX_BACKOFF_DELAY = 60      # Maximum delay in seconds between retries


def authenticate_google_cloud(project_id_override=None):
    """
    Obtains an authorized session using Application Default Credentials (ADC).

    Args:
        project_id_override (str): Optional project ID to use for the X-Goog-User-Project header.
                                   If not provided, uses the project ID discovered from ADC.

    Returns:
        tuple: (google.auth.transport.requests.AuthorizedSession, str)
               The authorized session and the project ID used.
    """
    logger.info("Authenticating with Google Cloud...")
    credentials, discovered_project = google.auth.default()
    
    # Prioritize: 1. Override, 2. Discovered Project, 3. Default "gus-sdl"
    project_id = project_id_override or discovered_project or "gus-sdl"
    
    # Standardize project_id: some environments might return underscores, but Chronicle expects hyphens.
    # Standard GCP project IDs use hyphens.
    if "_" in project_id:
        logger.warning(f"Project ID '{project_id}' contains underscores. Converting to hyphens.")
        project_id = project_id.replace("_", "-")

    logger.info(f"Authenticated with project: {project_id}")
    
    session = google_requests.AuthorizedSession(credentials)
    
    # The X-Goog-User-Project header is mandatory for Chronicle API when using user credentials.
    session.headers.update({"X-Goog-User-Project": project_id})
    
    return session, project_id


def getCuratedRuleSetCategories(auth_session, location, parent):
    """
    Fetches curated rule set categories.
    """
    url = f"https://{location}-chronicle.googleapis.com/v1alpha/{parent}/curatedRuleSetCategories?"
    response = auth_session.request('GET', url)

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error fetching rule set categories: {response.status_code} - {response.text}")
        return None


def getCuratedRuleSets(auth_session, location, parent, pageSize=50, filter=None, paginate=True):
    """
    Fetches curated rule sets.
    """
    all_rule_sets = []
    current_next_page_token = None

    while True:
        url = f"https://{location}-chronicle.googleapis.com/v1alpha/{parent}/curatedRuleSetCategories/-/curatedRuleSets"
        params = {"pageSize": pageSize}
        if filter:
            params["filter"] = filter
        if paginate and current_next_page_token:
            params["page_token"] = current_next_page_token

        retry_count = 0
        while retry_count < MAX_RETRIES:
            response = auth_session.request('GET', url, params=params)
            logger.debug(f"Request Parameters (RuleSets, Attempt {retry_count + 1}/{MAX_RETRIES}): {params}")

            if response.status_code == 200:
                response_json = response.json()
                if 'curatedRuleSets' in response_json:
                    all_rule_sets.extend(response_json['curatedRuleSets'])

                current_next_page_token = response_json.get('nextPageToken')
                break
            elif response.status_code == 429:
                delay = min(INITIAL_BACKOFF_DELAY * (2 ** retry_count), MAX_BACKOFF_DELAY)
                logger.warning(f"  Rate limit hit (429) for RuleSets. Retrying in {delay} seconds...")
                time.sleep(delay)
                retry_count += 1
            else:
                logger.error(f"  Error fetching curated rule sets: {response.status_code} - {response.text}")
                return None

        if retry_count == MAX_RETRIES:
            logger.error(f"  Max retries reached for RuleSets. Failed to get response for params: {params}")
            return None

        if not paginate or not current_next_page_token:
            break
    return all_rule_sets


def getFeaturedContentRules(auth_session, location, parent, pageSize=50, filter=None, paginate=True):
    """
    Fetches featured content rules.
    """
    all_rules = []
    current_next_page_token = None

    while True:
        url = f"https://{location}-chronicle.googleapis.com/v1alpha/{parent}/contentHub/featuredContentRules"
        params = {"pageSize": pageSize}
        if filter:
            params["filter"] = filter
        if paginate and current_next_page_token:
            params["page_token"] = current_next_page_token

        retry_count = 0
        while retry_count < MAX_RETRIES:
            response = auth_session.request('GET', url, params=params)
            logger.debug(f"Request Parameters (Rules, Attempt {retry_count + 1}/{MAX_RETRIES}): {params}")

            if response.status_code == 200:
                response_json = response.json()
                if 'featuredContentRules' in response_json:
                    all_rules.extend(response_json['featuredContentRules'])

                current_next_page_token = response_json.get('nextPageToken')
                break
            elif response.status_code == 429:
                delay = min(INITIAL_BACKOFF_DELAY * (2 ** retry_count), MAX_BACKOFF_DELAY)
                logger.warning(f"  Rate limit hit (429) for Rules. Retrying in {delay} seconds...")
                time.sleep(delay)
                retry_count += 1
            else:
                logger.error(f"  Error fetching featured content rules: {response.status_code} - {response.text}")
                return None

        if retry_count == MAX_RETRIES:
            logger.error(f"  Max retries reached for Rules. Failed to get response for params: {params}")
            return None

        if not paginate or not current_next_page_token:
            break
    return all_rules


def get_nested_rulesets_with_rules(auth_session, location, parent, ruleset_page_size=50, rules_page_size=50, paginate_rules_api=True, delay_between_rulesets=1):
    """
    Fetches all curated rule sets, then for each rule set, fetches its associated
    featured content rules, and combines them into a nested JSON structure.
    """
    logger.info("--- Starting data retrieval and nesting ---")

    all_rule_sets = getCuratedRuleSets(auth_session, location, parent, pageSize=ruleset_page_size, paginate=True)

    if not all_rule_sets:
        logger.error("Failed to retrieve any curated rule sets. Aborting.")
        return None

    sorted_rule_sets = sorted(all_rule_sets, key=lambda x: x.get('displayName', ''))
    nested_data = []

    for i, rule_set in enumerate(sorted_rule_sets):
        rule_set_display_name = rule_set.get('displayName')

        if not rule_set_display_name:
            logger.info(f"Skipping rule set with no displayName: {rule_set.get('name', 'N/A')}")
            continue

        logger.info(f"Processing Rule Set {i+1}/{len(sorted_rule_sets)}: {rule_set_display_name}")

        formatted_tactics_rs = [
            {"id": t.get('id', 'N/A'), "name": t.get('displayName', 'N/A')}
            for t in rule_set.get('tactics', [])
        ]
        formatted_techniques_rs = [
            {"id": t.get('id', 'N/A'), "name": t.get('displayName', 'N/A')}
            for t in rule_set.get('techniques', [])
        ]

        formatted_rule_set = {
            "ruleSetId": rule_set['name'].split('/')[-1],
            "ruleSetDisplayName": rule_set_display_name,
            "ruleSetDescription": rule_set.get('description', ''),
            "logSources": rule_set.get('logSources', []),
            "tactics": formatted_tactics_rs,
            "techniques": formatted_techniques_rs,
            "authors": rule_set.get('authors', [])
        }

        rule_filter = f'policy_name:"{rule_set_display_name}"'

        rules_for_this_set = getFeaturedContentRules(
            auth_session,
            location,
            parent,
            pageSize=rules_page_size,
            filter=rule_filter,
            paginate=paginate_rules_api
        )

        formatted_rules = []
        if rules_for_this_set:
            for rule in rules_for_this_set:
                content_metadata = rule.get('contentMetadata', {})
                curated_rule_content = rule.get('curatedRuleContent', {})

                formatted_tactics_rule = [
                    {"id": t.get('id', 'N/A'), "name": t.get('displayName', 'N/A')}
                    for t in curated_rule_content.get('tactics', [])
                ]
                formatted_techniques_rule = [
                    {"id": t.get('id', 'N/A'), "name": t.get('displayName', 'N/A')}
                    for t in curated_rule_content.get('techniques', [])
                ]

                formatted_rule = {
                    "ruleId": content_metadata.get('id'),
                    "ruleDisplayName": content_metadata.get('displayName'),
                    "ruleDescription": content_metadata.get('description', ''),
                    "ruleText": rule.get('ruleText', ''),
                    "categories": content_metadata.get('categories', []),
                    "precision": curated_rule_content.get('precision'),
                    "tactics": formatted_tactics_rule,
                    "techniques": formatted_techniques_rule
                }
                formatted_rules.append(formatted_rule)
        else:
            logger.info(f"  No rules found or an error occurred for '{rule_set_display_name}'.")

        formatted_rule_set['rules'] = formatted_rules
        nested_data.append(formatted_rule_set)

        if i < len(sorted_rule_sets) - 1 and delay_between_rulesets > 0:
            logger.info(f"  Waiting for {delay_between_rulesets} seconds before next rule set...")
            time.sleep(delay_between_rulesets)

    return nested_data


def generate_single_markdown_report(data, filename="chronicle_rules_report.md"):
    """
    Generates a single Markdown report from the nested rule set and rule data.
    """
    if not data:
        logger.info("No data provided to generate report. Skipping Markdown report generation.")
        return

    markdown_content = []
    markdown_content.append("# Chronicle Curated Rule Sets and Rules Report\n")
    markdown_content.append(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
    markdown_content.append(f"Total Rule Sets: {len(data)}\n")
    markdown_content.append("---\n")

    for i, rule_set in enumerate(data):
        rule_set_id = rule_set.get('ruleSetId', 'N/A')
        rule_set_display_name = rule_set.get('ruleSetDisplayName', 'Untitled Rule Set')
        rule_set_description = rule_set.get('ruleSetDescription', 'No description provided.')
        log_sources = ", ".join(rule_set.get('logSources', [])) if rule_set.get('logSources') else "N/A"
        authors_rs = ", ".join(rule_set.get('authors', [])) if rule_set.get('authors') else "N/A"

        markdown_content.append(f"## Rule Set: {rule_set_display_name} (ID: `{rule_set_id}`)\n")
        markdown_content.append(f"**Description:** {rule_set_description}\n\n")
        markdown_content.append(f"**Log Sources:** {log_sources}\n\n")

        markdown_content.append("**Tactics (Rule Set Level):**\n")
        if rule_set.get('tactics'):
            for t in rule_set['tactics']:
                markdown_content.append(f"  * **ID:** `{t.get('id', 'N/A')}`\n")
                markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
        else:
            markdown_content.append("  * N/A\n")
        markdown_content.append("\n")

        markdown_content.append("**Techniques (Rule Set Level):**\n")
        if rule_set.get('techniques'):
            for t in rule_set['techniques']:
                markdown_content.append(f"  * **ID:** `{t.get('id', 'N/A')}`\n")
                markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
        else:
            markdown_content.append("  * N/A\n")
        markdown_content.append("\n")

        markdown_content.append(f"**Authors:** {authors_rs}\n\n")

        rules = rule_set.get('rules', [])
        if rules:
            markdown_content.append(f"### Rules within this Rule Set ({len(rules)}):\n")
            for j, rule in enumerate(rules):
                rule_id = rule.get('ruleId', 'N/A')
                rule_display_name = rule.get('ruleDisplayName', 'Untitled Rule')
                rule_description = rule.get('ruleDescription', 'No description provided.')
                categories = ", ".join(rule.get('categories', [])) if rule.get('categories') else "N/A"
                precision = rule.get('precision', 'N/A')

                markdown_content.append(f"#### {j+1}. Rule: {rule_display_name} (ID: `{rule_id}`)\n")
                markdown_content.append(f"**Description:** {rule_description}\n\n")
                markdown_content.append(f"**Categories:** {categories}\n\n")
                markdown_content.append(f"**Precision:** {precision}\n\n")

                markdown_content.append("**Tactics (Rule Level):**\n")
                if rule.get('tactics'):
                    for t in rule['tactics']:
                        markdown_content.append(f"  * **ID:** `{t.get('id', 'N/A')}`\n")
                        markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
                else:
                    markdown_content.append("  * N/A\n")
                markdown_content.append("\n")

                markdown_content.append("**Techniques (Rule Level):**\n")
                if rule.get('techniques'):
                    for t in rule['techniques']:
                        markdown_content.append(f"  * **ID:** `{t.get('id', 'N/A')}`\n")
                        markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
                else:
                    markdown_content.append("  * N/A\n")
                markdown_content.append("\n")

                rule_text = rule.get('ruleText', 'No rule text available.')
                markdown_content.append("\n**Rule Text (YARA-L):**\n")
                markdown_content.append("```\n")
                markdown_content.append(rule_text.strip())
                markdown_content.append("\n```\n")

                if j < len(rules) - 1:
                    markdown_content.append("---\n")
        else:
            markdown_content.append("### No rules found for this Rule Set.\n")

        if i < len(data) - 1:
            markdown_content.append("\n***\n\n")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(markdown_content)
        logger.info(f"Markdown report successfully generated: {filename}")
    except IOError as e:
        logger.error(f"Error writing Markdown report to {filename}: {e}")


import re

def get_mitre_link(mitre_id):
    """Generates a MITRE ATT&CK link for a given ID."""
    if not mitre_id or mitre_id == 'N/A':
        return 'N/A'
    if mitre_id.startswith('TA'):
        return f"[{mitre_id}](https://attack.mitre.org/tactics/{mitre_id})"
    if mitre_id.startswith('T'):
        # Handle sub-techniques like T1556.006
        base_id = mitre_id.split('.')[0]
        return f"[{mitre_id}](https://attack.mitre.org/techniques/{base_id}/{mitre_id.split('.')[1] if '.' in mitre_id else ''})"
    return mitre_id

def extract_severity(rule_text):
    """Extracts severity from YARA-L meta section."""
    if not rule_text:
        return "N/A"
    # Look for severity = "High" or severity: "High"
    match = re.search(r'severity\s*[=:]\s*["\']?(\w+)["\']?', rule_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "N/A"

def generate_index_file(data, output_directory):
    """Generates a central index.md for all rule sets."""
    index_path = os.path.join(output_directory, "index.md")
    content = ["# Chronicle Curated Rule Sets Index\n\n"]
    content.append(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n")
    content.append("| Rule Set Name | ID | Rules Count | Log Sources |\n")
    content.append("| :--- | :--- | :--- | :--- |\n")

    for rule_set in data:
        name = rule_set.get('ruleSetDisplayName', 'Untitled')
        rs_id = rule_set.get('ruleSetId', 'N/A')
        count = len(rule_set.get('rules', []))
        sources = "<br>".join(rule_set.get('logSources', []))
        
        sanitized_name = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in name).strip()
        sanitized_name = "_".join(sanitized_name.split())
        filename = f"{sanitized_name}_{rs_id}.md"
        
        content.append(f"| [{name}]({filename}) | `{rs_id}` | {count} | {sources} |\n")

    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.writelines(content)
        logger.info(f"Central index created: {index_path}")
    except IOError as e:
        logger.error(f"Error writing index file: {e}")

def generate_individual_markdown_reports(data, output_directory="chronicle_rulesets_md_files"):
    """
    Generates a separate Markdown report file for each rule set with enhanced utility.
    """
    if not data:
        logger.info("No data provided to generate individual reports. Skipping Markdown report generation.")
        return

    os.makedirs(output_directory, exist_ok=True)
    logger.info(f"Generating enhanced individual Markdown files in: {output_directory}")

    for rule_set in data:
        rule_set_id = rule_set.get('ruleSetId', 'N/A')
        rule_set_display_name = rule_set.get('ruleSetDisplayName', 'Untitled Rule Set')

        sanitized_display_name = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in rule_set_display_name).strip()
        sanitized_display_name = "_".join(sanitized_display_name.split())

        filename = f"{sanitized_display_name}_{rule_set_id}.md"
        filepath = os.path.join(output_directory, filename)

        individual_markdown_content = []
        individual_markdown_content.append(f"# Rule Set: {rule_set_display_name} (ID: `{rule_set_id}`)\n")
        individual_markdown_content.append(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        individual_markdown_content.append("[Back to Index](index.md)\n")
        individual_markdown_content.append("---\n\n")

        rule_set_description = rule_set.get('ruleSetDescription', 'No description provided.')
        log_sources = ", ".join([f"`{s}`" for s in rule_set.get('logSources', [])]) if rule_set.get('logSources') else "N/A"
        authors_rs = ", ".join(rule_set.get('authors', [])) if rule_set.get('authors') else "N/A"

        individual_markdown_content.append(f"**Description:** {rule_set_description}\n\n")
        individual_markdown_content.append(f"**Log Sources:** {log_sources}\n\n")

        individual_markdown_content.append("**Tactics (Rule Set Level):**\n")
        if rule_set.get('tactics'):
            for t in rule_set['tactics']:
                link = get_mitre_link(t.get('id'))
                individual_markdown_content.append(f"  * **ID:** {link}\n")
                individual_markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
        else:
            individual_markdown_content.append("  * N/A\n")
        individual_markdown_content.append("\n")

        individual_markdown_content.append("**Techniques (Rule Set Level):**\n")
        if rule_set.get('techniques'):
            for t in rule_set['techniques']:
                link = get_mitre_link(t.get('id'))
                individual_markdown_content.append(f"  * **ID:** {link}\n")
                individual_markdown_content.append(f"    **Name:** {t.get('name', 'N/A')}\n")
        else:
            individual_markdown_content.append("  * N/A\n")
        individual_markdown_content.append("\n")

        individual_markdown_content.append(f"**Authors:** {authors_rs}\n\n")

        rules = rule_set.get('rules', [])
        if rules:
            individual_markdown_content.append(f"## Rules within this Rule Set ({len(rules)}):\n\n")
            for j, rule in enumerate(rules):
                rule_id = rule.get('ruleId', 'N/A')
                rule_display_name = rule.get('ruleDisplayName', 'Untitled Rule')
                rule_description = rule.get('ruleDescription', 'No description provided.')
                categories = ", ".join(rule.get('categories', [])) if rule.get('categories') else "N/A"
                precision = rule.get('precision', 'N/A')
                rule_text = rule.get('ruleText', '')
                severity = extract_severity(rule_text)

                severity_pills = {
                    "HIGH": "🔴 HIGH",
                    "CRITICAL": "🔥 CRITICAL",
                    "MEDIUM": "🟡 MEDIUM",
                    "LOW": "🟢 LOW",
                    "INFO": "ℹ️ INFO"
                }
                sev_display = severity_pills.get(severity, f"[{severity}]")

                individual_markdown_content.append(f"### {j+1}. {rule_display_name} \n")
                individual_markdown_content.append(f"**ID:** `{rule_id}` | **Severity:** {sev_display} | **Precision:** `{precision}`\n\n")
                individual_markdown_content.append(f"**Description:** {rule_description}\n\n")
                individual_markdown_content.append(f"**Categories:** {categories}\n\n")

                individual_markdown_content.append("**Tactics (Rule Level):**\n")
                if rule.get('tactics'):
                    for t in rule['tactics']:
                        link = get_mitre_link(t.get('id'))
                        individual_markdown_content.append(f"  * **ID:** {link} ({t.get('name', 'N/A')})\n")
                else:
                    individual_markdown_content.append("  * N/A\n")
                individual_markdown_content.append("\n")

                individual_markdown_content.append("**Techniques (Rule Level):**\n")
                if rule.get('techniques'):
                    for t in rule['techniques']:
                        link = get_mitre_link(t.get('id'))
                        individual_markdown_content.append(f"  * **ID:** {link} ({t.get('name', 'N/A')})\n")
                else:
                    individual_markdown_content.append("  * N/A\n")
                individual_markdown_content.append("\n")

                if rule_text:
                    individual_markdown_content.append("<details>\n")
                    individual_markdown_content.append("<summary><b>View Rule Text (YARA-L)</b></summary>\n\n")
                    individual_markdown_content.append("```yara\n")
                    individual_markdown_content.append(rule_text.strip())
                    individual_markdown_content.append("\n```\n")
                    individual_markdown_content.append("</details>\n\n")
                else:
                    individual_markdown_content.append("*No rule text available.*\n\n")

                if j < len(rules) - 1:
                    individual_markdown_content.append("---\n\n")
        else:
            individual_markdown_content.append("## No rules found for this Rule Set.\n\n")

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(individual_markdown_content)
            logger.debug(f"  Created: {filename}")
        except IOError as e:
            logger.error(f"  Error writing Markdown report to {filepath}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Chronicle Curated Detections Report Generator")
    parser.add_argument("--project_id", default=os.getenv("PROJECT_ID"), help="Google Cloud Project ID")
    parser.add_argument("--instance_id", default=os.getenv("INSTANCE_ID", "8cbac5ae-8267-4da7-b405-cdbc6fa3f1d5"), help="Chronicle Instance ID")
    parser.add_argument("--location", default=os.getenv("INSTANCE_LOCATION", "us"), help="Chronicle Instance Location")
    parser.add_argument("--ruleset_page_size", type=int, default=100, help="Page size for curated rule sets")
    parser.add_argument("--rules_page_size", type=int, default=1000, help="Page size for rules within a rule set")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between rule set processing")
    parser.add_argument("--paginate_rules", action="store_true", help="Attempt to paginate featured content rules")
    parser.add_argument("--output_jsonl", default="gemini_skill/references/chronicle_rulesets_with_rules.jsonl", help="Output JSONL filename")
    parser.add_argument("--output_dir", default="gemini_skill/references/chronicle_rulesets_md_files", help="Output directory for individual Markdown files")
    parser.add_argument("--zip_output", action="store_true", help="Zip the output directory")

    args = parser.parse_args()

    # Authenticate and resolve the project ID
    auth_session, resolved_project_id = authenticate_google_cloud(args.project_id)

    # Use the resolved project ID for the API parent path
    parent = f"projects/{resolved_project_id}/locations/{args.location}/instances/{args.instance_id}"

    combined_data = get_nested_rulesets_with_rules(
        auth_session,
        args.location,
        parent,
        ruleset_page_size=args.ruleset_page_size,
        rules_page_size=args.rules_page_size,
        paginate_rules_api=args.paginate_rules,
        delay_between_rulesets=args.delay
    )

    if combined_data:
        logger.info(f"--- Successfully retrieved and nested data for {len(combined_data)} rule sets ---")

        with open(args.output_jsonl, 'w', encoding='utf-8') as f:
            for entry in combined_data:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        logger.info(f"Combined data saved to {args.output_jsonl}")

        generate_individual_markdown_reports(combined_data, args.output_dir)
        generate_index_file(combined_data, args.output_dir)

        if args.zip_output:
            zip_filename = shutil.make_archive(args.output_dir, 'zip', args.output_dir)
            logger.info(f"Zip file created: {zip_filename}")

        # Print a snippet of the first entry for verification
        if combined_data:
            logger.info("\n--- Example of first nested entry ---")
            print(json.dumps(combined_data[0], indent=2, ensure_ascii=False))
    else:
        logger.error("--- Failed to retrieve combined data. ---")


if __name__ == "__main__":
    main()
