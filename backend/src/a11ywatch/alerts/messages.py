from collections.abc import Sequence
from dataclasses import dataclass

# Cap how many example issues we inline in an alert body.
_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class AlertMessage:
    subject: str
    body: str


def build_new_issues_message(
    *, project_name: str, base_url: str, new_count: int, sample: Sequence
) -> AlertMessage:
    """Customer-facing regression alert for newly detected accessibility issues.

    Vocabulary is deliberate: we report "issues" and send "regression alerts" from
    "monitoring". We describe what automated checks find; we never assert legal conformance.
    """
    noun = "issue" if new_count == 1 else "issues"
    subject = f"[A11yWatch] {new_count} new accessibility {noun} on {project_name}"

    lines = [
        f"Monitoring detected {new_count} new accessibility {noun} on {project_name} ({base_url}).",
        "",
        "Examples:",
    ]
    for v in list(sample)[:_SAMPLE_LIMIT]:
        lines.append(f"  - {v.rule_id} — {v.page_url}")
    lines += [
        "",
        "This is an automated regression alert from A11yWatch monitoring.",
        "See your dashboard for full documentation of these issues.",
    ]
    return AlertMessage(subject=subject, body="\n".join(lines))


def build_operator_alert_message(scan_id: str, error: str) -> AlertMessage:
    """Operator-facing alert for a scan that failed for good (never sent to customers)."""
    subject = f"[A11yWatch][operator] scan {scan_id} failed"
    body = "\n".join(
        [
            f"Scan {scan_id} failed after exhausting retries.",
            "",
            f"Error: {error}",
            "",
            "Investigate the worker logs and the target site availability.",
        ]
    )
    return AlertMessage(subject=subject, body=body)
