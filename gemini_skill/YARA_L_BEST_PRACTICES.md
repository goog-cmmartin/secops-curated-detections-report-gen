# YARA-L Best Practices (Derived from Curated Rules)

This guide summarizes effective patterns and standards used in Google SecOps Curated Detections.

## 1. Standard Outcome Variables
Curated rules follow a consistent naming convention for outcomes, making them easier to read and integrate with dashboards.

*   `$risk_score`: A numeric value (usually 0-100) representing the severity.
    *   *Example:* `$risk_score = max(35 + if($is_admin, 25))`
*   `$event_count`: Total number of events matched.
    *   *Example:* `$event_count = count_distinct($e.metadata.id)`
*   `$vendor_name` / `$product_name`: Always include these for context.
*   `$result`: Use standardized strings like `"succeeded"`, `"failed"`, or `"attempted"`.

## 2. Efficient Matching
*   **Match Windows:** Use appropriate windows (e.g., `5m`, `1h`, `24h`). For UEBA, `24h` is common.
*   **Match Keys:** Match on the smallest unique set of entities (e.g., `$user, $ip` or `$access_key, $instance_id`).

## 3. Advanced Logic Patterns
### Multi-Event Correlation
To detect a "Delete then Create" pattern (like AMI replacement):
1. Define `$e1` (Deletion) and `$e2` (Creation).
2. Ensure ordering: `$e1.metadata.event_timestamp.seconds < $e2.metadata.event_timestamp.seconds`.
3. Use a short match window (e.g., `5m`).

### UEBA & Metrics
Use the `metrics` namespace to compare current behavior against historical baselines.
*   *Standard Threshold:* 6 standard deviations above average is a common "high signal" threshold in curated rules.
*   *Check for existence:* Always verify `$historical_threshold > 0` to avoid division by zero or noisy alerts on new entities.

## 4. Metadata (Meta Section)
Every rule should include:
*   `rule_name`: Human-readable name.
*   `description`: Clear explanation of what is detected.
*   `severity`: High, Medium, Low, or Info.
*   `tactic` / `technique`: MITRE ATT&CK IDs.

## 5. Filter Logic
*   **Muting:** Check for `$e.security_result.detection_fields["mute"] != "MUTED"` to respect ingestion-time muting.
*   **Success Check:** Most TTP rules focus on successful actions: `$e.security_result.action = "ALLOW"`.
