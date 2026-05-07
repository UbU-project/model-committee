import re
from pathlib import Path

from pydantic import BaseModel

DECISION_HEADING_RE = re.compile(r"^## (UBU-D[0-9]{4}): (.+)$")


class Decision(BaseModel):
    decision_id: str
    title: str


def parse_decisions_text(text: str) -> list[Decision]:
    return [
        Decision(decision_id=match.group(1), title=match.group(2))
        for line in text.splitlines()
        if (match := DECISION_HEADING_RE.match(line))
    ]


def parse_decisions_file(path: Path) -> list[Decision]:
    return parse_decisions_text(Path(path).read_text(encoding="utf-8"))
