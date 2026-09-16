import re

from model_committee.responses.schemas import ConsistencyIssue

# CommonMark fenced code blocks: up to three spaces of indent, then three or more
# backticks or tildes, then an optional info string.
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CANONICAL_HEADING_RE = re.compile(r"^## UBU-[QD][0-9]{4}:")


def code_fence_warnings(filename: str, text: str) -> list[ConsistencyIssue]:
    """Warn about code fences that swallow canonical content.

    The parsers read headings line by line and ignore fences, so a missing closing
    fence never breaks parsing. It does break rendering: every heading below it is
    shown as code until the next bare fence. Counting fences is not enough, because
    an unclosed ```text pairs with the next opener's info string and the count stays
    even. A closing fence cannot carry an info string, so an info-string fence inside
    an open block is the signature of a missing close.
    """
    issues: list[ConsistencyIssue] = []
    open_marker: str | None = None
    open_line = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if open_marker is None:
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                open_marker = match.group(1)
                open_line = line_number
            continue
        if (
            match
            and match.group(1)[0] == open_marker[0]
            and len(match.group(1)) >= len(open_marker)
        ):
            if not match.group(2).strip():
                open_marker = None
                continue
            issues.append(
                ConsistencyIssue(
                    code="CODE_FENCE_UNCLOSED",
                    message=(
                        f"{filename}:{open_line} code fence looks unclosed: line {line_number} "
                        "opens another fenced block inside it."
                    ),
                )
            )
        if CANONICAL_HEADING_RE.match(line):
            item_id = line[3:12]
            issues.append(
                ConsistencyIssue(
                    code="HEADING_INSIDE_CODE_FENCE",
                    message=(
                        f"{filename}:{line_number} heading {item_id} is inside the code "
                        f"fence opened at line {open_line}."
                    ),
                    question_id=item_id if item_id.startswith("UBU-Q") else None,
                    decision_id=item_id if item_id.startswith("UBU-D") else None,
                )
            )
    if open_marker is not None:
        issues.append(
            ConsistencyIssue(
                code="CODE_FENCE_UNCLOSED",
                message=f"{filename}:{open_line} code fence is never closed.",
            )
        )
    return issues
