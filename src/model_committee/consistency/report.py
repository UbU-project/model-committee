import json

from model_committee.responses.schemas import ConsistencyReport


def format_consistency_report(report: ConsistencyReport) -> str:
    return json.dumps(report.model_dump(), indent=2) + "\n"


def hard_failure_summary(report: ConsistencyReport) -> str:
    lines = ["hard consistency failure:"]
    lines.extend(f"  {issue.code}: {issue.message}" for issue in report.hard_failures)
    return "\n".join(lines)
