import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from model_committee.constants import ALLOWED_PATCH_FILES

QUESTION_RE = re.compile(r"^UBU-Q[0-9]{4}$")
DECISION_RE = re.compile(r"^UBU-D[0-9]{4}$")


class WorkProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    provider_id: str
    model_name: str
    question_id: str
    base_commit: str
    summary: str
    rationale: str
    changed_files: list[str]
    patch: str
    commit_message: str
    validation_notes: list[str]
    new_questions_added: list[str]
    questions_resolved: list[str]
    decisions_added: list[str]
    requires_human_review: bool

    @field_validator("question_id", *("new_questions_added", "questions_resolved"))
    @classmethod
    def validate_question_ids(cls, value):
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not QUESTION_RE.match(item):
                raise ValueError(f"invalid question id: {item}")
        return value

    @field_validator("decisions_added")
    @classmethod
    def validate_decision_ids(cls, value: list[str]) -> list[str]:
        for item in value:
            if not DECISION_RE.match(item):
                raise ValueError(f"invalid decision id: {item}")
        return value

    @field_validator("changed_files")
    @classmethod
    def validate_changed_files(cls, value: list[str]) -> list[str]:
        invalid = sorted(set(value) - ALLOWED_PATCH_FILES)
        if invalid:
            raise ValueError(f"changed files outside allowlist: {', '.join(invalid)}")
        return value

    @field_validator("patch")
    @classmethod
    def validate_patch(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("patch must be non-empty")
        if "diff --git" not in value and "--- a/" not in value:
            raise ValueError("patch must contain at least one diff --git or --- a/ header")
        return value

    @field_validator("commit_message")
    @classmethod
    def validate_commit_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("commit_message must be non-empty")
        return value


class ProposalScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    score: int = Field(ge=0, le=100)
    patch_applies: bool
    implements_selected_work: bool
    preserves_question_schema: bool
    avoids_unnecessary_scope: bool
    decomposition_quality: Literal["none", "good", "bad", "not_applicable"]
    risks: list[str]
    required_fixes: list[str]
    rationale: str


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: list[ProposalScore]
    selected_proposal_id: str
    selection_rationale: str

    @model_validator(mode="after")
    def validate_selected_is_scored(self) -> "ScoreResult":
        if self.selected_proposal_id not in {score.proposal_id for score in self.scores}:
            raise ValueError("selected_proposal_id must match one scored proposal_id")
        return self


class SchemaValidationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    message: str | None = None
    response_path: str | None = None
    stderr_path: str | None = None


class ScoreMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    author_provider: str
    scorer_provider: str
    score: int | None = Field(default=None, ge=0, le=100)
    valid: bool
    rationale: str
    implements_selected_work: bool = True
    avoids_unnecessary_scope: bool = True
    required_fixes: list[str]
    risks: list[str]
    schema_validation: SchemaValidationStatus


class DisagreementFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["warning", "critical"]
    proposal_id: str | None = None
    message: str


class ProposalScoreAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    author_provider: str
    cross_score_count: int
    score_mean: float | None = None
    score_spread: int | None = None
    frontier_score_gap: int | None = None
    disagreement_flags: list[DisagreementFlag] = Field(default_factory=list)


class QuorumResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    human_review_required: bool
    selected_proposal_id: str | None = None
    selected_score: float | None = None
    selected_cross_score_count: int = 0
    blocked_reasons: list[str] = Field(default_factory=list)
    manual_override: bool = False


class ConsistencyIssue(BaseModel):
    code: str
    message: str
    question_id: str | None = None
    decision_id: str | None = None


class ConsistencyReport(BaseModel):
    status: Literal["passed", "failed"]
    hard_failures: list[ConsistencyIssue]
    warnings: list[ConsistencyIssue]
    question_count: int
    decision_count: int
    dependency_edges: list[tuple[str, str]]


class RankedQuestion(BaseModel):
    question_id: str
    title: str
    answerability_score: int
    automation_likelihood_score: int | None
    importance_score: int | None
    risk_score: int | None
    rank_reason: str


class RankingReport(BaseModel):
    status: Literal["ok"]
    ranked_questions: list[RankedQuestion]
    selected_question_id: str | None
