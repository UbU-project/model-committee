import re
from pathlib import Path

from pydantic import BaseModel

from model_committee.errors import ParseError
from model_committee.markdown.metadata_parser import require_valid_metadata_line

QUESTION_HEADING_RE = re.compile(r"^## (UBU-Q[0-9]{4}): (.+)$")

STATUS_VALUES = {"Open", "Solved", "Deferred", "Superseded", "Archived", "Decomposed"}
PRIORITY_VALUES = {"MVP blocker", "MVP important", "Post-MVP", "Research"}
PHASE_VALUES = {"Phase 1", "Phase 2", "Phase 3", "Post-MVP"}
DECISION_TYPE_VALUES = {
    "Scope",
    "Data model",
    "Process",
    "Governance",
    "Product",
    "Security",
    "Architecture",
}
AUTO_ELIGIBILITY_VALUES = {"Auto eligible", "Human approval required", "Human only"}
SENTINELS = {"TBD", "Never", "None", "Unresolved"}


class QuestionMetadata(BaseModel):
    status: str
    priority: str
    phase: str
    decision_type: str
    auto_choice_eligibility: str
    importance_score: int | None
    automation_likelihood_score: int | None
    risk_score: int | None
    answerability_score: int | None
    depends_on: list[str]
    blocks: list[str]
    resolved_by: list[str]
    last_scored: str
    scored_from_commit: str
    supersedes: list[str] = []
    superseded_by: list[str] = []
    decomposes: list[str] = []
    decomposed_into: list[str] = []


class Question(BaseModel):
    question_id: str
    title: str
    metadata: QuestionMetadata
    block: str
    has_current_direction: bool


def _parse_score(value: str) -> int | None:
    if value == "TBD":
        return None
    try:
        score = int(value)
    except ValueError as exc:
        raise ParseError(f"Invalid score value: {value}") from exc
    if score < 0 or score > 100:
        raise ParseError(f"Invalid score value: {value}")
    return score


def _parse_refs(value: str, allowed_sentinel: str = "None") -> list[str]:
    if value in SENTINELS or value == allowed_sentinel:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _require_enum(field: str, value: str, allowed: set[str]) -> str:
    if value not in allowed:
        raise ParseError(f"Invalid enum value for {field}: {value}")
    return value


def _metadata_from_line(line: str) -> QuestionMetadata:
    raw = require_valid_metadata_line(line)
    return QuestionMetadata(
        status=_require_enum("Status", raw["Status"], STATUS_VALUES),
        priority=_require_enum("Priority", raw["Priority"], PRIORITY_VALUES),
        phase=_require_enum("Phase", raw["Phase"], PHASE_VALUES),
        decision_type=_require_enum("Decision type", raw["Decision type"], DECISION_TYPE_VALUES),
        auto_choice_eligibility=_require_enum(
            "Auto-choice eligibility",
            raw["Auto-choice eligibility"],
            AUTO_ELIGIBILITY_VALUES,
        ),
        importance_score=_parse_score(raw["Importance score"]),
        automation_likelihood_score=_parse_score(raw["Automation-likelihood score"]),
        risk_score=_parse_score(raw["Risk score"]),
        answerability_score=_parse_score(raw["Answerability score"]),
        depends_on=_parse_refs(raw["Depends on"]),
        blocks=_parse_refs(raw["Blocks"]),
        resolved_by=_parse_refs(raw["Resolved by"], allowed_sentinel="Unresolved"),
        last_scored=raw["Last scored"],
        scored_from_commit=raw["Scored from commit"],
        supersedes=_parse_refs(raw.get("Supersedes", "None")),
        superseded_by=_parse_refs(raw.get("Superseded by", "None")),
        decomposes=_parse_refs(raw.get("Decomposes", "None")),
        decomposed_into=_parse_refs(raw.get("Decomposed into", "None")),
    )


def parse_questions_text(text: str) -> list[Question]:
    lines = text.splitlines()
    starts: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        match = QUESTION_HEADING_RE.match(line)
        if match:
            starts.append((idx, match.group(1), match.group(2)))

    questions: list[Question] = []
    for pos, (start, question_id, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        block_lines = lines[start:end]
        metadata_line = next((line for line in block_lines[1:] if line.strip()), "")
        try:
            metadata = _metadata_from_line(metadata_line)
        except ParseError as exc:
            raise ParseError(f"{question_id}: {exc}") from exc
        questions.append(
            Question(
                question_id=question_id,
                title=title,
                metadata=metadata,
                block="\n".join(block_lines).rstrip() + "\n",
                has_current_direction="### Current direction" in "\n".join(block_lines),
            )
        )
    return questions


def parse_questions_file(path: Path) -> list[Question]:
    return parse_questions_text(Path(path).read_text(encoding="utf-8"))


_ANSWERABILITY_SCORE_RE = re.compile(r"(Answerability score:)\s*\S+")
_LAST_SCORED_RE = re.compile(r"(Last scored:)\s*\S+")


def _update_metadata_line(line: str, *, answerability_score: int, last_scored: str) -> str:
    line = _ANSWERABILITY_SCORE_RE.sub(rf"\g<1> {answerability_score}", line, count=1)
    line = _LAST_SCORED_RE.sub(rf"\g<1> {last_scored}", line, count=1)
    return line


def update_question_scores(
    text: str,
    score_by_id: dict[str, int],
    scored_date: str,
) -> str:
    """Update Answerability score and Last scored fields for open questions.

    Only questions whose IDs appear in score_by_id are modified.
    Scored from commit is intentionally left unchanged.
    """
    lines = text.splitlines(keepends=True)
    pending_question_id: str | None = None
    result: list[str] = []
    for line in lines:
        match = QUESTION_HEADING_RE.match(line.rstrip("\n\r"))
        if match:
            pending_question_id = match.group(1)
            result.append(line)
        elif pending_question_id is not None and line.strip():
            if pending_question_id in score_by_id:
                line = _update_metadata_line(
                    line,
                    answerability_score=score_by_id[pending_question_id],
                    last_scored=scored_date,
                )
            pending_question_id = None
            result.append(line)
        else:
            result.append(line)
    return "".join(result)
