# Google SecOps Curated Detections Report Generator

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A robust tool to fetch, nest, and document Google Security Operations (Chronicle) Curated Detections. This tool converts raw API data into high-quality Markdown reports and includes a specialized **Gemini CLI Skill** for intelligent rule lookup and YARA-L best practices.

## 🚀 Features

- **Automated Data Retrieval:** Fetches all curated rule sets and their associated rules from the Chronicle API.
- **Nested JSONL Output:** Generates a structured `chronicle_rulesets_with_rules.jsonl` file for downstream automation.
- **Enhanced Markdown Reports:** Creates individual, human-readable reports for every rule set featuring:
    - 🔴 **Severity Badges** (parsed from YARA-L meta).
    - 🔗 **MITRE ATT&CK Hyperlinks** for Tactics and Techniques.
    - 📂 **Collapsible YARA-L Code Blocks** for better readability.
    - 🧩 **Log Source Highlighting.**
- **Central Navigation:** Automatically generates an `index.md` hub linking all reports.
- **Gemini CLI Integration:** Includes a custom agent skill to turn Gemini CLI into a curated detections expert.

## 📋 Prerequisites

1.  **Python 3.6+**
2.  **Google Cloud SDK (gcloud):** [Install here](https://cloud.google.com/sdk/docs/install).
3.  **Authentication:**
    ```bash
    gcloud auth application-default login
    ```

## 🛠️ Installation

```bash
git clone https://github.com/your-username/secops-curated-rules-report-gen.git
cd secops-curated-rules-report-gen
pip install -r requirements.txt
```

## 📖 Usage

### Generate Reports
```bash
./curated_detections_report_generator.py --project_id "your-project" --instance_id "your-instance-guid"
```

**Common Options:**
- `--location`: Chronicle region (default: `us`).
- `--output_dir`: Custom directory for Markdown files.
- `--zip_output`: Create a zip archive of all generated reports.

### Environment Variables
You can also set these to avoid passing flags:
```bash
export PROJECT_ID="your-project"
export INSTANCE_ID="your-instance-guid"
export INSTANCE_LOCATION="us"
```

## 🤖 Gemini CLI Skill: Curated Detections Agent

This repository includes a specialized skill that enables Gemini CLI to act as an expert on these rules. 

> **Important:** To use the skill, you must first run the generator script (see "Usage" above) to fetch the rule data from your Chronicle instance. The script will automatically populate the `gemini_skill/references/` folder, which the agent uses as its knowledge base.

### How to Activate
```bash
gemini --activate-skill ./gemini_skill/SKILL.md
```

### Capabilities
- **Intelligent Lookup:** *"Show me rules related to T1078 (Valid Accounts)."*
- **Best Practices:** *"What are the standard outcome variables for curated rules?"*
- **Code Retrieval:** Access full YARA-L code directly through the chat interface.

## 📁 Repository Structure

- `curated_detections_report_generator.py`: The main execution script.
- `gemini_skill/`: Logic and knowledge base for the Gemini CLI Agent.
- `chronicle_rulesets_md_files/`: (Generated) Human-readable reports.
- `YARA_L_BEST_PRACTICES.md`: Distilled standards from Google's curated detections.

## ⚖️ License

Distributed under the Apache License 2.0. See `LICENSE` for more information.

---
*Disclaimer: This is not an official Google product.*
