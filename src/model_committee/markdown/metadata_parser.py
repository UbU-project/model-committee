from dataclasses import dataclass

from model_committee.errors import ParseError

REQUIRED_LABELS = [
    "Status:",
    "Priority:",
    "Phase:",
    "Decision type:",
    "Auto-choice eligibility:",
    "Importance score:",
    "Automation-likelihood score:",
    "Risk score:",
    "Answerability score:",
    "Depends on:",
    "Blocks:",
    "Resolved by:",
    "Last scored:",
    "Scored from commit:",
]

OPTIONAL_LABELS = ["Supersedes:", "Superseded by:", "Decomposes:", "Decomposed into:"]
ALL_LABELS = REQUIRED_LABELS + OPTIONAL_LABELS


@dataclass(frozen=True)
class ParsedMetadata:
    values: dict[str, str]
    errors: list[str]


def parse_metadata_line(line: str) -> ParsedMetadata:
    labels = []
    errors: list[str] = []
    for label in ALL_LABELS:
        start = line.find(label)
        if start != -1:
            second = line.find(label, start + len(label))
            if second != -1:
                errors.append(f"Duplicate metadata field: {label.removesuffix(':')}")
            labels.append((start, label))

    labels.sort()
    values: dict[str, str] = {}
    present = [label for _, label in labels]
    for required in REQUIRED_LABELS:
        if required not in present:
            errors.append(f"Missing required field: {required.removesuffix(':')}")

    required_positions = [present.index(label) for label in REQUIRED_LABELS if label in present]
    if required_positions != sorted(required_positions):
        errors.append("Metadata labels are out of order")

    if labels and line[: labels[0][0]].strip():
        errors.append(f"Unknown or unparsed metadata segment near: {line[: labels[0][0]].strip()}")

    allowed_seen = REQUIRED_LABELS.copy()
    optional_seen = [label for label in OPTIONAL_LABELS if label in present]
    allowed_seen.extend(optional_seen)
    if present != allowed_seen:
        errors.append("Metadata labels are out of order")

    for idx, (start, label) in enumerate(labels):
        end = labels[idx + 1][0] if idx + 1 < len(labels) else len(line)
        values[label.removesuffix(":")] = line[start + len(label) : end].strip()

    if labels:
        last_label = labels[-1][1].removesuffix(":")
        if last_label not in values:
            errors.append("Could not parse final metadata field")
    else:
        errors.append("No metadata labels found")

    if not labels and line.strip():
        errors.append(f"Unknown or unparsed metadata segment near: {line.strip()}")
    elif "Auto-choice eligibility:" not in present and "Auto choice eligibility" in line:
        errors.append("Unknown or unparsed metadata segment near: Auto choice eligibility")

    return ParsedMetadata(values=values, errors=list(dict.fromkeys(errors)))


def require_valid_metadata_line(line: str) -> dict[str, str]:
    parsed = parse_metadata_line(line)
    if parsed.errors:
        raise ParseError("; ".join(parsed.errors))
    return parsed.values
