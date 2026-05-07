import json

from model_committee.responses.schemas import ConsistencyReport


def format_consistency_report(report: ConsistencyReport) -> str:
    return json.dumps(report.model_dump(), indent=2) + "\n"
