# model-committee v0.1 Implementation Contract

Status: Accepted implementation contract  
Project: `model-committee`  
Target repository: `https://github.com/UbU-project/model-committee`  
Canonical design repository: `https://github.com/UbU-project/ubu-design`

---

## 1. Purpose

`model-committee` is a bootstrap automation tool for the UbU project.

It reads the canonical `ubu-design` repository, selects answerable open questions, asks model providers to propose concrete changesets, scores those proposals, validates patches, and writes reviewable artifacts.

`model-committee` is not the canonical decision engine. Accepted design state exists only when committed to the canonical design repository.

The first implementation is intentionally narrow, local, inspectable, and testable.

---

## 2. v0.1 Scope

`model-committee v0.1` must implement:

- parse `OPEN_QUESTIONS.md`;
- run consistency checks;
- rank answerable questions;
- generate Codex work prompts;
- launch Codex CLI work provider;
- run configured Ollama work models sequentially by priority;
- import and validate candidate work proposals;
- mechanically validate patches;
- generate Codex scoring prompts;
- launch Codex CLI scoring provider;
- select the winning patch;
- write `selected.patch`, `commit_message.txt`, `review.md`, and logs;
- support fake provider mode for tests;
- include a `doctor` command for environment checks;
- include a `version` command.

---

## 3. Explicitly Out of Scope

`model-committee v0.1` must not implement:

- direct OpenAI API calls;
- direct Anthropic API calls;
- direct Gemini API calls;
- GitHub API calls;
- auto-merge;
- auto-push;
- automatic pull request creation;
- adaptive model scoring;
- readiness score updates to `README.md`;
- derived `README.md` / `OUTREACH.md` consistency updates;
- automatic patch application;
- arbitrary network calls outside approved providers;
- direct mutation of canonical repo files by Codex.

`work-select` must not apply patches in v0.1. It only writes review artifacts.

---

## 4. Python Tooling

Use this stack:

```text
Python: 3.12+
Package manager: uv
CLI: argparse
Schemas/validation: pydantic
HTTP: httpx
Testing: pytest
Lint/format: ruff
Patch validation: git apply --check via subprocess
Markdown parsing: custom parser, not Markdown AST
```

No direct OpenAI, Anthropic, Gemini, or GitHub SDK dependencies are allowed in v0.1.

`httpx` may be used only by the Ollama provider and only for the configured local Ollama `base_url`.

---

## 5. Repository Layout

Use this layout:

```text
model-committee/
  README.md
  IMPLEMENTATION_CONTRACT.md
  pyproject.toml

  config/
    models.example.json

  schemas/
    work_proposal.schema.json
    score_result.schema.json

  prompts/
    work_prompt.md
    score_prompt.md

  src/
    model_committee/
      __init__.py
      __main__.py
      cli.py
      config.py
      constants.py
      errors.py

      markdown/
        __init__.py
        decisions_parser.py
        questions_parser.py
        metadata_parser.py

      consistency/
        __init__.py
        checker.py
        question_graph.py
        decision_refs.py
        report.py

      ranking/
        __init__.py
        answerability.py
        ranker.py

      providers/
        __init__.py
        base.py
        codex.py
        ollama.py
        fake.py

      prompts/
        __init__.py
        work_prompt.py
        score_prompt.py

      responses/
        __init__.py
        json_extract.py
        schemas.py
        schema_files.py

      patches/
        __init__.py
        extract.py
        validate.py

      runs/
        __init__.py
        layout.py
        manifest.py
        review.py

      orchestration/
        __init__.py
        check.py
        rank.py
        work_generate.py
        work_score.py
        work_select.py
        run_loop.py

  tests/
    fixtures/
      valid_repo/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_missing_answerability_score/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_unknown_label/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_priority_value/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_missing_required_field/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_nonexistent_dependency/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_dependency_cycle/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_nonexistent_decision_reference/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      invalid_duplicate_question_id/
        DESIGN.md
        DECISIONS.md
        OPEN_QUESTIONS.md

      fake_responses/
        codex_work_response.valid.json
        ollama_response.valid.txt
        codex_score_response.valid.json
        codex_score_response.selects_invalid.json
        work_response.invalid_json.txt
        work_response.empty_patch.json
        work_response.forbidden_file_patch.json

    test_questions_parser.py
    test_metadata_parser.py
    test_consistency.py
    test_answerability.py
    test_json_extract.py
    test_patch_validate.py
    test_cli.py
    test_fake_provider_flow.py
    test_no_network_policy.py
```

---

## 6. `pyproject.toml`

Use this base file:

```toml
[project]
name = "model-committee"
version = "0.1.0"
description = "Bootstrap model committee automation for the UbU project"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.0",
  "httpx>=0.27"
]

[project.scripts]
model-committee = "model_committee.cli:main"

[dependency-groups]
dev = [
  "pytest>=8.0",
  "ruff>=0.6"
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 7. CLI Commands

The CLI command is:

```bash
model-committee
```

### 7.1 `check`

```bash
model-committee check --repo ../ubu-design [--config config/models.json] [--runs-dir ./runs]
```

Behavior:

- parse `DESIGN.md`, `DECISIONS.md`, and `OPEN_QUESTIONS.md`;
- validate question metadata;
- validate unique question IDs;
- validate unique decision IDs;
- validate dependency references;
- validate dependency DAG has no cycles;
- validate `Resolved by` references;
- print or write a consistency report;
- exit `0` if no hard failures;
- exit `2` if hard consistency failure.

### 7.2 `rank`

```bash
model-committee rank --repo ../ubu-design [--config config/models.json] [--runs-dir ./runs]
```

Behavior:

- run consistency checks first;
- compute answerability for each question;
- rank eligible questions;
- print ranked list;
- optionally write `ranking_report.json`;
- exit `0` on success;
- exit `2` on hard consistency failure.

### 7.3 `work-generate`

```bash
model-committee work-generate \
  --repo ../ubu-design \
  --question UBU-Q0038 \
  [--config config/models.json] \
  [--runs-dir ./runs] \
  [--fake-providers]
```

Behavior:

- run consistency checks;
- verify selected question exists;
- verify selected question is answerable or eligible for decomposition;
- create run directory;
- snapshot canonical files;
- copy schema files into run directory;
- render Codex work prompt;
- run Codex provider unless `--fake-providers` is set;
- run enabled Ollama models sequentially by priority unless `--fake-providers` is set;
- load canned fake responses when `--fake-providers` is set;
- import responses;
- validate work proposals;
- extract and validate patches;
- write parsed proposals and patch files;
- set manifest status to `waiting_for_score`;
- print run ID.

### 7.4 `work-score`

```bash
model-committee work-score --run runs/<run-id> [--config config/models.json] [--fake-providers]
```

Behavior:

- load run manifest;
- load valid work proposals;
- load patch validation results;
- render Codex scoring prompt;
- run Codex scoring provider unless `--fake-providers` is set;
- load canned fake scoring response when `--fake-providers` is set;
- validate scorer JSON;
- write `parsed/score_result.json`;
- set manifest status to `scored`.

### 7.5 `work-select`

```bash
model-committee work-select --run runs/<run-id>
```

Behavior:

- load `score_result.json`;
- validate `selected_proposal_id` exists;
- validate selected proposal passed mechanical patch validation;
- copy selected patch to `patches/selected.patch`;
- write `commit_message.txt`;
- write `review.md`;
- set manifest status to `selected`.

If `selected_proposal_id` refers to a proposal that failed mechanical validation:

- fail with exit code `7`;
- do not write `selected.patch`;
- write `review.md` explaining the failure if possible.

### 7.6 `run-loop`

```bash
model-committee run-loop --repo ../ubu-design [--config config/models.json] [--runs-dir ./runs]
```

Behavior:

1. `check`
2. `rank`
3. pick top-ranked eligible question
4. `work-generate`
5. `work-score`
6. `work-select`

On failure, exit with the failing phase’s exit code and leave partial run logs intact.

### 7.7 `doctor`

```bash
model-committee doctor --config config/models.json --repo ../ubu-design [--runs-dir ./runs]
```

Checks:

- Python version is `>= 3.12`;
- `git` is available;
- `codex` is available;
- `codex exec --help` contains required flags:
  - `--skip-git-repo-check`
  - `--cd`
  - `--model`
  - `--sandbox`
  - `--output-schema`
  - `--json`
  - `-o` or `--output-last-message`
- Ollama `base_url` is reachable;
- configured Ollama models are installed;
- target repo files exist:
  - `DESIGN.md`
  - `DECISIONS.md`
  - `OPEN_QUESTIONS.md`
- runs directory is writable.

`doctor` should warn, but not fail, if it cannot verify that Codex web search is disabled.

`model-committee v0.1` does not inspect, modify, or enforce Codex config.

### 7.8 `version`

```bash
model-committee version
```

Output:

```text
model-committee 0.1.0
```

---

## 8. Exit Codes

Use these exit codes:

```text
0 = success
1 = ordinary runtime error
2 = hard consistency failure
3 = provider failure / missing response
4 = invalid model output
5 = no valid patch proposals
6 = patch validation failed
7 = no acceptable scorer selection
8 = user canceled external process
```

Codex nonzero exit codes map to:

```text
codex returncode != 0 → provider failure / model-committee exit 3
```

`8` is reserved for future interactive/manual providers.

---

## 9. Config Format

Default config path:

```text
config/models.json
```

Example config file:

```json
{
  "codex": {
    "enabled": true,
    "command": "codex",
    "model": "gpt-5.5",
    "timeout_seconds": 3600,
    "weight": 1.0,
    "sandbox": "read-only",
    "use_json_events": true,
    "working_directory": "../ubu-design",
    "prompt_input_mode": "stdin"
  },
  "ollama": {
    "base_url": "http://localhost:11434",
    "models": [
      {
        "name": "sam860/deepseek-r1-0528-qwen3:8b",
        "enabled": true,
        "priority": 1,
        "weight": 0.35,
        "max_context_tokens": 32768,
        "timeout_seconds": 1800,
        "temperature": 0.2,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_predict": 4096,
        "notes": "Primary local reasoning fallback"
      },
      {
        "name": "qooba/qwen3-coder-30b-a3b-instruct:q3_k_m",
        "enabled": true,
        "priority": 2,
        "weight": 0.3,
        "max_context_tokens": 65536,
        "timeout_seconds": 3600,
        "temperature": 0.2,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_predict": 4096,
        "notes": "Large local coding proposal model; may be slow/heavy"
      },
      {
        "name": "vaultbox/qwen3.5-uncensored:27b",
        "enabled": true,
        "priority": 3,
        "weight": 0.25,
        "max_context_tokens": 32768,
        "timeout_seconds": 3600,
        "temperature": 0.2,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_predict": 4096,
        "notes": "Large local alternate reasoning/model-diversity proposal model; may be slow/heavy"
      }
    ]
  }
}
```

---

## 10. Error Class Names

Define these exception classes in `errors.py`:

```python
class ModelCommitteeError(Exception): ...
class ConfigError(ModelCommitteeError): ...
class ParseError(ModelCommitteeError): ...
class ConsistencyError(ModelCommitteeError): ...
class ProviderError(ModelCommitteeError): ...
class ModelOutputError(ModelCommitteeError): ...
class PatchValidationError(ModelCommitteeError): ...
class SelectionError(ModelCommitteeError): ...
```

---

## 11. Codex Provider Contract

Codex CLI is the primary provider for:

- work proposal generation;
- work scoring.

Codex must be invoked only through subprocess.

Codex must not directly modify repository files in v0.1.

Codex produces JSON work proposals and JSON score results. Patches are validated and selected by `model-committee`, then written as review artifacts.

### 11.1 Codex Runtime Behavior

Runtime Codex calls must:

- use `codex exec`;
- always pass `--skip-git-repo-check`;
- pass prompt text through stdin with `-`;
- use `--cd ../ubu-design`;
- use `--model gpt-5.5`;
- use `--sandbox read-only`;
- use `--json`;
- use `--output-schema`;
- use `-o` / `--output-last-message`;
- save stdout JSONL event stream;
- save stderr;
- validate final JSON output with Pydantic.

Runtime Codex calls must not pass:

```text
--ask-for-approval
--disable web_search
```

The installed Codex CLI does not support `--ask-for-approval`.

The installed Codex CLI reports the old web-search feature flag as deprecated. `model-committee v0.1` does not manage Codex web-search configuration. If web search must be disabled, that is handled through Codex config/profile outside `model-committee`.

### 11.2 Work Generation Argv

Use this argv construction for work generation:

```python
[
    "codex",
    "exec",
    "--skip-git-repo-check",
    "--cd", "../ubu-design",
    "--model", "gpt-5.5",
    "--sandbox", "read-only",
    "--json",
    "--output-schema", "runs/<run-id>/schemas/work_proposal.schema.json",
    "-o", "runs/<run-id>/responses/codex_work_response.json",
    "-"
]
```

### 11.3 Scoring Argv

Use this argv construction for scoring:

```python
[
    "codex",
    "exec",
    "--skip-git-repo-check",
    "--cd", "../ubu-design",
    "--model", "gpt-5.5",
    "--sandbox", "read-only",
    "--json",
    "--output-schema", "runs/<run-id>/schemas/score_result.schema.json",
    "-o", "runs/<run-id>/responses/codex_score_response.json",
    "-"
]
```

### 11.4 Python Subprocess Execution

Use this execution behavior:

```python
subprocess.run(
    args,
    input=prompt_path.read_text(encoding="utf-8"),
    text=True,
    stdout=events_file,
    stderr=stderr_file,
    timeout=config.timeout_seconds,
    check=False,
)
```

Then:

```text
if returncode != 0: raise ProviderError
if output_path missing: raise ProviderError
parse output_path as JSON
validate with Pydantic
```

### 11.5 Codex Event Log Handling

Codex `--json` stdout is an event log stream.

v0.1 behavior:

- save stdout exactly to `codex_work_events.jsonl` or `codex_score_events.jsonl`;
- do not parse event logs for correctness in v0.1;
- verify only that the final response file exists and parses as JSON;
- optionally summarize token usage later if event structure stabilizes.

### 11.6 Codex Final Output Validation

Codex final-output validation steps:

1. Codex process exits `0`.
2. Expected output file exists.
3. Output file is valid JSON.
4. Output validates against the same Pydantic model used internally.
5. For work proposals, patch validation runs afterward.
6. For score results, `selected_proposal_id` must match a valid proposal.

No JSON extraction is used for Codex outputs.

---

## 12. Ollama Provider Contract

Ollama is a secondary work proposal provider.

Ollama does not score work in v0.1.

Ollama models run sequentially by priority.

If Ollama responses finish within timeout and validate, include them in Codex scoring.

If an Ollama provider fails, log it and continue if at least one valid Codex proposal exists.

### 12.1 Ollama Request Shape

Endpoint:

```text
POST http://localhost:11434/api/generate
```

Request body:

```json
{
  "model": "<model name>",
  "prompt": "<prompt text>",
  "stream": false,
  "options": {
    "temperature": 0.2,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "num_predict": 4096,
    "num_ctx": 32768
  }
}
```

Expected response field:

```text
response
```

### 12.2 Ollama JSON Extraction

Ollama outputs use JSON extraction rules:

1. Strip leading/trailing whitespace.
2. Try to parse the entire response as JSON.
3. If that fails, accept exactly one Markdown fenced code block.
4. The fence may be ```json or plain ```.
5. Parse the fence contents as JSON.
6. If multiple fenced blocks exist, fail.
7. If no valid JSON object exists, fail.
8. No repair attempts in v0.1.

---

## 13. Provider Interface

Define protocol-like interfaces:

```python
class WorkProvider(Protocol):
    provider_id: str

    def generate_work_proposal(
        self,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
    ) -> WorkProposal: ...


class ScoreProvider(Protocol):
    provider_id: str

    def score_work_proposals(
        self,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
    ) -> ScoreResult: ...
```

Codex implements both `WorkProvider` and `ScoreProvider`.

Ollama implements only `WorkProvider` in v0.1.

Fake provider mode provides deterministic test implementations.

---

## 14. Prompt Templates

Use exact variable names:

```text
{question_id}
{question_title}
{question_block}
{base_commit}
{design_md}
{decisions_md}
{open_questions_md}
{work_proposal_schema}
{score_result_schema}
{candidate_proposals_json}
{patch_validation_results_json}
```

Warn if total prompt exceeds `100,000` characters.

Do not auto-truncate in v0.1.

### 14.1 `prompts/work_prompt.md`

````markdown
# Model-Committee Work Proposal Request

You are participating in the UbU `model-committee` process.

Your task is to produce one concrete work proposal as strict JSON.

Do not return prose outside the JSON object.

## Selected question

Question ID: `{question_id}`  
Question title: `{question_title}`  
Base commit: `{base_commit}`

```markdown
{question_block}
```

## Canonical design files

### DESIGN.md

```markdown
{design_md}
```

### DECISIONS.md

```markdown
{decisions_md}
```

### OPEN_QUESTIONS.md

```markdown
{open_questions_md}
```

## JSON Schema

Your output must satisfy this schema:

```json
{work_proposal_schema}
```

## Requirements

- Return exactly one JSON object.
- All fields are required.
- Arrays may be empty.
- The patch must be a full git-diff-style patch.
- The patch may modify only:
  - `DESIGN.md`
  - `DECISIONS.md`
  - `OPEN_QUESTIONS.md`
- Do not modify `README.md`, `OUTREACH.md`, hidden files, scripts, code files, or generated logs.
- Preserve the single-line metadata format in `OPEN_QUESTIONS.md`.
- Use the existing `UBU-Qxxxx` and `UBU-Dxxxx` numbering conventions.
- Prefer minimal, auditable changesets.
- If the selected question is blocked, propose decomposition only if it produces replacement questions with fewer, simpler, or no dependencies.
- If the selected question is already partially resolved, narrow or clarify it rather than pretending it is fully unresolved.

Return only JSON.
`````

### 14.2 `prompts/score_prompt.md`

````markdown
# Model-Committee Work Scoring Request

You are scoring candidate work proposals for the UbU `model-committee` process.

Return exactly one JSON object. Do not return prose outside the JSON object.

## Selected question

Question ID: `{question_id}`  
Question title: `{question_title}`  
Base commit: `{base_commit}`

```markdown
{question_block}
```

## Candidate proposals

```json
{candidate_proposals_json}
```

## Mechanical validation results

```json
{patch_validation_results_json}
```

## JSON Schema

Your output must satisfy this schema:

```json
{score_result_schema}
```

## Scoring requirements

Score each proposal from 0 to 100.

Consider:

- whether the patch applies cleanly;
- whether it implements the selected work;
- whether it preserves the question schema;
- whether it avoids unnecessary scope;
- whether it modifies only allowed files;
- whether it creates useful decomposition if decomposition occurs;
- whether it introduces new risks;
- whether required fixes remain.

Rules:

- `selected_proposal_id` must refer to one scored proposal.
- There is no minimum acceptable score in v0.1.
- Manual override is not allowed in v0.1.
- Prefer a patch that is valid, minimal, auditable, and directly responsive.
- Do not select a proposal whose patch failed mechanical validation unless all proposals failed.

Return only JSON.
````

---

## 15. JSON Schema Files

### 15.1 `schemas/work_proposal.schema.json`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "proposal_id",
    "provider_id",
    "model_name",
    "question_id",
    "base_commit",
    "summary",
    "rationale",
    "changed_files",
    "patch",
    "commit_message",
    "validation_notes",
    "new_questions_added",
    "questions_resolved",
    "decisions_added",
    "requires_human_review"
  ],
  "properties": {
    "proposal_id": { "type": "string" },
    "provider_id": { "type": "string" },
    "model_name": { "type": "string" },
    "question_id": { "type": "string", "pattern": "^UBU-Q[0-9]{4}$" },
    "base_commit": { "type": "string" },
    "summary": { "type": "string" },
    "rationale": { "type": "string" },
    "changed_files": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["DESIGN.md", "DECISIONS.md", "OPEN_QUESTIONS.md"]
      }
    },
    "patch": { "type": "string" },
    "commit_message": { "type": "string" },
    "validation_notes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "new_questions_added": {
      "type": "array",
      "items": { "type": "string", "pattern": "^UBU-Q[0-9]{4}$" }
    },
    "questions_resolved": {
      "type": "array",
      "items": { "type": "string", "pattern": "^UBU-Q[0-9]{4}$" }
    },
    "decisions_added": {
      "type": "array",
      "items": { "type": "string", "pattern": "^UBU-D[0-9]{4}$" }
    },
    "requires_human_review": { "type": "boolean" }
  }
}
```

### 15.2 `schemas/score_result.schema.json`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "scores",
    "selected_proposal_id",
    "selection_rationale"
  ],
  "properties": {
    "scores": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "proposal_id",
          "score",
          "patch_applies",
          "implements_selected_work",
          "preserves_question_schema",
          "avoids_unnecessary_scope",
          "decomposition_quality",
          "risks",
          "required_fixes",
          "rationale"
        ],
        "properties": {
          "proposal_id": { "type": "string" },
          "score": { "type": "integer", "minimum": 0, "maximum": 100 },
          "patch_applies": { "type": "boolean" },
          "implements_selected_work": { "type": "boolean" },
          "preserves_question_schema": { "type": "boolean" },
          "avoids_unnecessary_scope": { "type": "boolean" },
          "decomposition_quality": {
            "type": "string",
            "enum": ["none", "good", "bad", "not_applicable"]
          },
          "risks": {
            "type": "array",
            "items": { "type": "string" }
          },
          "required_fixes": {
            "type": "array",
            "items": { "type": "string" }
          },
          "rationale": { "type": "string" }
        }
      }
    },
    "selected_proposal_id": { "type": "string" },
    "selection_rationale": { "type": "string" }
  }
}
```

---

## 16. Pydantic Model Names and Locations

### `responses/schemas.py`

Define:

```python
class WorkProposal(BaseModel): ...
class ProposalScore(BaseModel): ...
class ScoreResult(BaseModel): ...
class ConsistencyIssue(BaseModel): ...
class ConsistencyReport(BaseModel): ...
class RankedQuestion(BaseModel): ...
class RankingReport(BaseModel): ...
```

### `config.py`

Define:

```python
class ModelCommitteeConfig(BaseModel): ...
class CodexConfig(BaseModel): ...
class OllamaConfig(BaseModel): ...
class OllamaModelConfig(BaseModel): ...
```

### `markdown/questions_parser.py`

Define:

```python
class Question(BaseModel): ...
class QuestionMetadata(BaseModel): ...
```

### `runs/manifest.py`

Define:

```python
class RunManifest(BaseModel): ...
class RunStatus(str, Enum): ...
```

---

## 17. Work Proposal Pydantic Contract

Required fields:

```python
class WorkProposal(BaseModel):
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
```

Rules:

```text
- All fields are required.
- Arrays may be empty.
- patch must be a full git-diff-style patch.
- patch must be non-empty.
- patch must contain at least one `diff --git` header.
- question_id must match UBU-Q[0-9]{4}.
- decisions_added entries must match UBU-D[0-9]{4}.
- changed_files must be a subset of the v0.1 allowlist.
- commit_message must be non-empty.
```

Commit message behavior:

```text
commit_message.txt is copied from selected proposal commit_message.
It must be non-empty.
It should be <= 72 characters on the first line, but v0.1 only warns if longer.
```

---

## 18. Scorer Pydantic Contract

Required fields:

```python
class ProposalScore(BaseModel):
    proposal_id: str
    score: int
    patch_applies: bool
    implements_selected_work: bool
    preserves_question_schema: bool
    avoids_unnecessary_scope: bool
    decomposition_quality: Literal["none", "good", "bad", "not_applicable"]
    risks: list[str]
    required_fixes: list[str]
    rationale: str

class ScoreResult(BaseModel):
    scores: list[ProposalScore]
    selected_proposal_id: str
    selection_rationale: str
```

Rules:

```text
- score is an integer from 0 to 100.
- There is no minimum acceptable score in v0.1.
- manual override is not allowed in v0.1.
- selected_proposal_id must match one scored proposal_id.
- risks and required_fixes arrays may be empty.
```

---

## 19. `OPEN_QUESTIONS.md` Parser Contract

### 19.1 Question Heading

Question headings match:

```regex
^## (UBU-Q[0-9]{4}): (.+)$
```

### 19.2 Decision Heading

Decision headings match:

```regex
^## (UBU-D[0-9]{4}): (.+)$
```

### 19.3 Metadata Format

`OPEN_QUESTIONS.md` metadata may be stored as a single physical line.

Metadata fields always appear in this exact order:

```text
Status:
Priority:
Phase:
Decision type:
Auto-choice eligibility:
Importance score:
Automation-likelihood score:
Risk score:
Answerability score:
Depends on:
Blocks:
Resolved by:
Last scored:
Scored from commit:
```

Optional fields may appear after `Scored from commit:`:

```text
Supersedes:
Superseded by:
Decomposes:
Decomposed into:
```

Labels are case-sensitive and exact.

### 19.4 Metadata Parsing Algorithm

Use label-boundary parsing:

```text
1. Given the metadata line, find exact label positions in required order.
2. The value for each field is the substring after its label and before the next label.
3. Trim whitespace.
4. Reject if any required label is missing.
5. Reject if any required label is duplicated.
6. Reject if labels are out of order.
7. Reject if unknown text remains before the first label or after the last recognized optional field.
```

### 19.5 Allowed Enum Values

```text
Status:
Open | Solved | Deferred | Superseded | Archived | Decomposed

Priority:
MVP blocker | MVP important | Post-MVP | Research

Phase:
Phase 1 | Phase 2 | Phase 3 | Post-MVP

Decision type:
Scope | Data model | Process | Governance | Product | Security | Architecture

Auto-choice eligibility:
Auto eligible | Human approval required | Human only
```

### 19.6 Sentinel Values

Allowed sentinel values:

```text
TBD
Never
None
Unresolved
```

### 19.7 Multiple References

Multiple references are comma-separated IDs, optionally with spaces.

Examples:

```text
Depends on: None
Depends on: UBU-Q0032
Depends on: UBU-Q0032, UBU-Q0039

Resolved by: Unresolved
Resolved by: UBU-D0063
Resolved by: UBU-D0057, UBU-D0058, UBU-D0059
```

---

## 20. Consistency Checks

Hard failures:

```text
duplicate question ID
duplicate decision ID
missing required metadata field
invalid enum value
dependency points to nonexistent question
circular question dependency
Resolved by points to nonexistent decision
selected ordinary-work question has unresolved dependencies
patch modifies forbidden files
patch does not apply cleanly
```

Warnings:

```text
score is TBD
question has no Current direction
DECISIONS.md exceeds soft token budget
question count increases but decomposition rationale exists
README.md or OUTREACH.md may be stale
commit message first line exceeds 72 characters
prompt exceeds 100,000 characters
```

### 20.1 Hard Failure Codes

```text
DUPLICATE_QUESTION_ID
DUPLICATE_DECISION_ID
MISSING_REQUIRED_METADATA
INVALID_ENUM_VALUE
NONEXISTENT_DEPENDENCY
QUESTION_DEPENDENCY_CYCLE
NONEXISTENT_DECISION_REFERENCE
SELECTED_QUESTION_BLOCKED
PATCH_FORBIDDEN_FILE
PATCH_DOES_NOT_APPLY
```

### 20.2 Warning Codes

```text
QUESTION_SCORE_TBD
QUESTION_HAS_NO_CURRENT_DIRECTION
DECISIONS_SOFT_TOKEN_BUDGET_EXCEEDED
QUESTION_COUNT_INCREASE_WITH_DECOMPOSITION
DERIVED_FILE_STALE
COMMIT_MESSAGE_FIRST_LINE_LONG
PROMPT_SIZE_WARNING
```

### 20.3 Consistency Report Schema

Example:

```json
{
  "status": "passed",
  "hard_failures": [],
  "warnings": [
    {
      "code": "QUESTION_SCORE_TBD",
      "message": "UBU-Q0038 has TBD scores.",
      "question_id": "UBU-Q0038"
    }
  ],
  "question_count": 40,
  "decision_count": 69,
  "dependency_edges": [
    ["UBU-Q0038", "UBU-Q0032"]
  ]
}
```

---

## 21. Ranking and Answerability

### 21.1 Answerability Score

Compute answerability:

```text
100 = Depends on: None
90  = all dependencies have Status: Solved
50  = question has unresolved dependencies but Auto-choice eligibility: Auto eligible
0   = question has unresolved dependencies and is not auto-eligible for decomposition
```

A question is solved only if:

```text
Status: Solved
```

Partial resolution text is not enough to treat an open question as solved.

### 21.2 Work Selection Gate

```text
Ordinary work may select only answerability >= 90.
Decomposition work may select answerability == 50.
Blocked questions with answerability 0 are not selected.
```

### 21.3 TBD Score Handling

In parsed objects and reports:

```text
TBD → null
```

For sorting:

```text
automation-likelihood null → -1
importance null → -1
risk null → 101
```

### 21.4 Ranking Sort

Use this ranking behavior:

```python
ranked = sorted(
    open_questions,
    key=lambda q: (
        q.answerability_score,
        q.automation_likelihood_score or -1,
        open_dependent_count[q.question_id],
        q.importance_score or -1,
        -(q.risk_score or 101),
        -int(q.question_id.removeprefix("UBU-Q")),
    ),
    reverse=True,
)
```

`open_dependent_count` is the number of other currently open questions that directly
list the candidate in `Depends on`.

### 21.5 Ranking Report Schema

Example:

```json
{
  "status": "ok",
  "ranked_questions": [
    {
      "question_id": "UBU-Q0038",
      "title": "Changeset-Based Work Phase",
      "answerability_score": 100,
      "automation_likelihood_score": null,
      "importance_score": null,
      "risk_score": null,
      "rank_reason": "No unresolved dependencies; MVP-important model-committee work item."
    }
  ],
  "selected_question_id": "UBU-Q0038"
}
```

---

## 22. Run Directory Layout

Default run directory root:

```text
./runs
```

Configurable with:

```text
--runs-dir PATH
```

Run ID format:

```text
YYYYMMDDTHHMMSSZ-UBU-Qxxxx
```

Example:

```text
20260506T153000Z-UBU-Q0038
```

Run layout:

```text
runs/
  <timestamp>-<question-id>/
    manifest.json
    snapshot/
      DESIGN.md
      DECISIONS.md
      OPEN_QUESTIONS.md
    schemas/
      work_proposal.schema.json
      score_result.schema.json
    prompts/
      codex_work_prompt.md
      ollama_work_prompt.md
      codex_score_prompt.md
    responses/
      codex_work_response.json
      codex_work_events.jsonl
      codex_work_stderr.txt
      ollama_<safe_model_name>_response.txt
      codex_score_response.json
      codex_score_events.jsonl
      codex_score_stderr.txt
    parsed/
      codex_work_proposal.json
      ollama_<safe_model_name>_proposal.json
      score_result.json
    patches/
      codex.patch
      ollama_<safe_model_name>.patch
      selected.patch
    review.md
    commit_message.txt
```

---

## 23. Manifest Schema

Recommended `manifest.json` structure:

```json
{
  "run_id": "20260506T153000Z-UBU-Q0038",
  "created_at_utc": "2026-05-06T15:30:00Z",
  "repo_path": "../ubu-design",
  "base_commit": "b1a33588af97fefbc011bb2521252c5b72da5cc9",
  "selected_question_id": "UBU-Q0038",
  "phase": "work-generate",
  "config_path": "config/models.json",
  "status": "in_progress",
  "commands": [
    "model-committee work-generate --repo ../ubu-design --question UBU-Q0038"
  ],
  "providers_attempted": [
    "codex",
    "ollama:sam860__deepseek-r1-0528-qwen3--8b"
  ],
  "providers_succeeded": [],
  "providers_failed": []
}
```

Run statuses:

```text
created
in_progress
waiting_for_score
scored
selected
failed
```

---

## 24. Schema File Module

Implement `responses/schema_files.py`.

Required functions:

```python
def write_work_proposal_schema(path: Path) -> None: ...

def write_score_result_schema(path: Path) -> None: ...

def copy_schema_files_to_run(run_dir: Path) -> SchemaPaths: ...
```

Define:

```python
class SchemaPaths(BaseModel):
    work_proposal_schema: Path
    score_result_schema: Path
```

---

## 25. Provider IDs and Safe Model Names

Codex provider ID:

```text
codex
```

Codex model name:

```text
codex:gpt-5.5
```

Ollama provider IDs:

```text
ollama:<safe_model_name>
```

Safe model name function:

```text
lowercase
replace "/" with "__"
replace ":" with "--"
replace spaces with "_"
remove other unsafe filesystem characters
```

Examples:

```text
sam860/deepseek-r1-0528-qwen3:8b
→ sam860__deepseek-r1-0528-qwen3--8b

qooba/qwen3-coder-30b-a3b-instruct:q3_k_m
→ qooba__qwen3-coder-30b-a3b-instruct--q3_k_m

vaultbox/qwen3.5-uncensored:27b
→ vaultbox__qwen3.5-uncensored--27b
```

---

## 26. Generated File Naming

Use:

```text
prompts/codex_work_prompt.md
prompts/ollama_work_prompt.md
prompts/codex_score_prompt.md

responses/codex_work_response.json
responses/codex_work_events.jsonl
responses/codex_work_stderr.txt
responses/ollama_<safe_model_name>_response.txt
responses/codex_score_response.json
responses/codex_score_events.jsonl
responses/codex_score_stderr.txt

parsed/codex_work_proposal.json
parsed/ollama_<safe_model_name>_proposal.json
parsed/score_result.json

patches/codex.patch
patches/ollama_<safe_model_name>.patch
patches/selected.patch
```

---

## 27. Patch Validation

Allowed changed files:

```text
DESIGN.md
DECISIONS.md
OPEN_QUESTIONS.md
```

Forbidden:

```text
README.md
OUTREACH.md
LICENSE
code files
scripts
hidden files
generated logs inside ubu-design
absolute paths
paths containing ..
files outside the allowlist
```

Mechanical validation steps:

```text
1. Extract patch from proposal.
2. Verify patch is non-empty.
3. Verify patch contains at least one `diff --git` header.
4. Extract changed file paths from diff headers.
5. Verify every changed file is in the allowlist:
   - DESIGN.md
   - DECISIONS.md
   - OPEN_QUESTIONS.md
6. Reject paths with `../`.
7. Reject absolute paths.
8. Reject hidden file paths.
9. Copy repo to temporary validation directory or use git worktree.
10. Run: git apply --check <patch>
11. If git apply --check fails, proposal is invalid for selection.
```

Allowed path forms:

```text
a/DESIGN.md
b/DESIGN.md
DESIGN.md
```

---

## 28. `work-select` Behavior

`work-select` does not apply patches.

It only writes:

```text
patches/selected.patch
commit_message.txt
review.md
```

If the selected proposal failed mechanical validation:

```text
- fail with exit code 7
- do not write selected.patch
- write review.md explaining the failure if possible
```

---

## 29. `review.md` Format

Recommended generated review artifact:

````markdown
# Model-Committee Review

Run: `20260506T153000Z-UBU-Q0038`  
Question: `UBU-Q0038`  
Base commit: `b1a33588af97fefbc011bb2521252c5b72da5cc9`  
Selected proposal: `codex-work-001`

## Selected summary

Define the changeset-based work phase for model-committee v0.1.

## Selection rationale

Highest score, cleanest scope, and no required fixes.

## Changed files

- `DECISIONS.md`
- `DESIGN.md`
- `OPEN_QUESTIONS.md`

## Validation

- Patch applies: yes
- Patch allowlist passed: yes
- Question schema preserved: yes

## Risks

None reported.

## Next manual steps

```bash
git -C ../ubu-design apply "$(pwd)/runs/20260506T153000Z-UBU-Q0038/patches/selected.patch"
git -C ../ubu-design commit -F "$(pwd)/runs/20260506T153000Z-UBU-Q0038/commit_message.txt"
```
````

---

## 30. Fake Provider Mode

Add:

```bash
model-committee work-generate \
  --repo tests/fixtures/valid_repo \
  --question UBU-Q0001 \
  --fake-providers
```

Behavior:

```text
- do not call Codex
- do not call Ollama
- load canned fake responses from tests/fixtures/fake_responses/
- run normal JSON validation
- run normal patch validation
- write normal run artifacts
```

Fake response fixture files:

```text
tests/fixtures/fake_responses/
  codex_work_response.valid.json
  ollama_response.valid.txt
  codex_score_response.valid.json
  codex_score_response.selects_invalid.json
  work_response.invalid_json.txt
  work_response.empty_patch.json
  work_response.forbidden_file_patch.json
```

---

## 31. Test Fixtures

Required parser fixture categories:

```text
valid_repo
invalid_missing_answerability_score
invalid_unknown_label
invalid_priority_value
invalid_missing_required_field
invalid_nonexistent_dependency
invalid_dependency_cycle
invalid_nonexistent_decision_reference
invalid_duplicate_question_id
```

Example valid `OPEN_QUESTIONS.md` block:

```markdown
## UBU-Q0001: Example Question

Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process Auto-choice eligibility: Auto eligible Importance score: TBD Automation-likelihood score: TBD Risk score: TBD Answerability score: TBD Depends on: None Blocks: None Resolved by: Unresolved Last scored: Never Scored from commit: None

### Question

What should happen?

### Resolution

Unresolved.
```

Example invalid unknown label:

```markdown
## UBU-Q9998: Bad Label

Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process Auto choice eligibility: Auto eligible Importance score: TBD Automation-likelihood score: TBD Risk score: TBD Answerability score: TBD Depends on: None Blocks: None Resolved by: Unresolved Last scored: Never Scored from commit: None
```

Expected error:

```text
Missing required field: Auto-choice eligibility
Unknown or unparsed metadata segment near: Auto choice eligibility
```

---

## 32. Golden Fake-Provider End-to-End Test

Add one golden test.

Input:

```text
- fixture repo
- selected question UBU-Q0001
- fake Codex work response
- fake Ollama response
- fake Codex score response
```

Expected:

```text
- manifest status = selected
- patches/selected.patch exists
- commit_message.txt exists
- review.md exists
- no real Codex calls occurred
- no real Ollama calls occurred
```

---

## 33. No-Network Policy

`model-committee` itself may only communicate with:

```text
- local Ollama base_url
- Codex CLI subprocess
```

It must not call:

```text
- GitHub
- OpenAI APIs directly
- Anthropic APIs
- Gemini APIs
- arbitrary HTTP URLs
```

Implementation guidance:

```text
- no OpenAI SDK dependency
- no Anthropic SDK dependency
- no GitHub client dependency
- httpx only used for Ollama base_url
- Codex is invoked only by subprocess
```

Add a no-network policy test.

A simple v0.1 test may monkeypatch `httpx.Client` / `httpx.post` and assert only configured Ollama URLs are used.

---

## 34. Path Handling Policy

Use:

```text
All run artifact paths are relative to the model-committee repo unless absolute --runs-dir is provided.
The target repo path may be relative or absolute.
Patch validation must resolve paths and reject:
- absolute paths inside patches
- paths containing ..
- hidden file paths
- files outside the allowlist
```

---

## 35. Test Commands

Required validation commands:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Optional fix command:

```bash
uv run ruff format .
```

---

## 36. Initial Code Generation Command

After this file is committed or present in the existing `model-committee` repository, generate the implementation with:

```bash
cat > generate_v0_1.prompt.md <<'EOF'
Implement model-committee v0.1 according to IMPLEMENTATION_CONTRACT.md.

Use IMPLEMENTATION_CONTRACT.md as the authority.

Implement:
- repository layout and missing files
- pyproject.toml updates if needed
- config/models.example.json
- JSON schema files
- argparse CLI
- Pydantic models
- OPEN_QUESTIONS.md parser
- consistency checks
- ranking and answerability
- Codex provider
- Ollama provider
- fake provider mode
- doctor command
- version command
- patch validation
- run directory handling
- manifest handling
- review artifact generation
- tests and fixtures

Do not implement features explicitly out of scope.
Do not add direct OpenAI, Anthropic, Gemini, or GitHub API integrations.
Do not add arbitrary network access.
Use httpx only for the configured Ollama base_url.
Keep implementation minimal, testable, and aligned with the contract.
EOF

codex exec \
  --skip-git-repo-check \
  --cd "$(pwd)" \
  --model gpt-5.5 \
  --sandbox workspace-write \
  --json \
  -o codex_generate_v0_1_summary.md \
  - \
  < generate_v0_1.prompt.md \
  > codex_generate_v0_1_events.jsonl \
  2> codex_generate_v0_1_stderr.txt
```

Do not use:

```text
--ask-for-approval
--disable web_search
```

---

## 37. Post-Generation Checks

Run:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

If fixes are needed, use:

```bash
cat > fix_tests.prompt.md <<'EOF'
Fix the failing tests, lint errors, and formatting issues in this repository.

Use IMPLEMENTATION_CONTRACT.md as the authority.
Do not add out-of-scope features.
Make the smallest changes needed to pass:
- uv run pytest
- uv run ruff check .
- uv run ruff format --check .
EOF

codex exec \
  --skip-git-repo-check \
  --cd "$(pwd)" \
  --model gpt-5.5 \
  --sandbox workspace-write \
  --json \
  -o codex_fix_tests_summary.md \
  - \
  < fix_tests.prompt.md \
  > codex_fix_tests_events.jsonl \
  2> codex_fix_tests_stderr.txt
```

Before committing:

```bash
git status
git diff
```

Then commit manually:

```bash
git add .
git commit -m "Implement model-committee v0.1 skeleton"
```
