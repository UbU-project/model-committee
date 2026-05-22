# model-committee v0.2 Implementation Contract

Status: Accepted implementation contract  
Project: `model-committee`  
Target repository: `https://github.com/UbU-project/model-committee`  
Canonical design repository: `https://github.com/UbU-project/ubu-design`

---

## 1. Purpose

`model-committee` is a bootstrap automation tool for the UbU project.

It reads the canonical `ubu-design` repository, selects answerable open questions,
asks approved model providers to propose concrete changesets, cross-scores those
proposals, validates patches, and writes reviewable artifacts.

`model-committee` is not the canonical decision engine. Accepted design state
exists only when a human operator commits to the canonical design repository.

---

## 2. v0.2 Scope

`model-committee v0.2` must implement the v0.1 local/testable workflow plus:

- Claude Code CLI as a second frontier provider for work proposal generation;
- Claude Code CLI as a schema-native scoring provider;
- Codex and Claude Code cross-scoring;
- explicit score matrix artifacts;
- quorum policy based only on valid cross-scores from different frontier providers;
- disagreement flags in `review.md` and `manifest.json`;
- manifest fields for provider attempts, provider successes, score matrix,
  cross-score counts, score aggregates, disagreement flags, quorum result, and
  artifact-publication status;
- Claude Code doctor checks;
- operator-run artifact publication commands in generated `review.md`.

Ollama remains a local work-proposal provider and does not score in v0.2.

Fake provider mode must remain deterministic and must not call Codex, Claude, or
Ollama.

---

## 3. Explicitly Out Of Scope

`model-committee v0.2` must not implement:

- direct OpenAI API calls;
- direct Anthropic API calls;
- direct Gemini API calls;
- GitHub API calls;
- auto-merge;
- auto-push;
- automatic pull request creation;
- automatic artifact publication;
- automatic patch application to `ubu-design`;
- adaptive model weights;
- multi-turn Claude Code sessions;
- full Association automation;
- UbU planning-kernel work.

`model-committee` MUST NOT directly call Anthropic APIs.

`model-committee` MAY invoke approved external CLI subprocesses, including
Claude Code, when explicitly enabled in configuration. Such subprocesses may
perform their own network/API calls according to their upstream authentication
and billing configuration.

`model-committee` remains responsible for orchestration, schemas, validation,
manifests, review artifacts, provider logging, and final selection logic.

---

## 4. Tooling And Network Policy

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

No OpenAI, Anthropic, Gemini, or GitHub SDK dependency is allowed.

`httpx` may be used only by the Ollama provider and only for a configured local
Ollama `base_url`.

Approved external model subprocesses:

- Codex CLI;
- Claude Code CLI.

---

## 5. CLI Commands

The CLI command is:

```bash
model-committee
```

Commands:

- `check`
- `rank`
- `work-generate`
- `work-score`
- `work-select`
- `run-loop`
- `doctor`
- `version`

`work-select` must not apply patches. It writes review artifacts only.

---

## 6. Exit Codes

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
9 = human review required by quorum/disagreement policy
```

---

## 7. Config Format

Default config path:

```text
config/models.json
```

Required top-level config blocks:

- `codex`
- `claude`
- `ollama`

Claude Code config is analogous to Codex config and must include:

```json
{
  "claude": {
    "enabled": true,
    "command": "claude",
    "model": "sonnet",
    "timeout_seconds": 3600,
    "weight": 1.0,
    "tools": "",
    "max_turns": 1,
    "bare": true,
    "minimum_version": "2.1.146",
    "doctor_smoke_test": false,
    "max_budget_usd": null
  }
}
```

`tools` defaults to the empty string so Claude Code provider calls receive the
complete prompt content from `model-committee` and do not need repository tool
access.

---

## 8. Provider Contracts

### 8.1 Codex

Codex remains an approved frontier provider for:

- work proposal generation;
- work proposal scoring.

Codex must be invoked only through subprocess.

Codex must not directly modify repository files.

Codex output is schema-validated with Pydantic. No JSON extraction is used for
Codex outputs.

### 8.2 Claude Code

Claude Code is an approved frontier provider for:

- work proposal generation;
- work proposal scoring.

Claude Code must be invoked in non-interactive print mode.

Claude Code must prefer schema-native structured output with `--json-schema`.
Do not use Ollama-style JSON extraction for Claude Code.

Required default behavior:

- use `--output-format json`;
- use `--json-schema`;
- parse `structured_output` when present;
- treat missing `structured_output` as provider failure;
- treat schema mismatch as provider failure;
- use `--tools ""` by default;
- do not rely on `--allowedTools` as a restriction mechanism;
- use `--max-turns 1`;
- capture stdout, stderr, exit code, timeout, model name, provider name,
  schema-validation result, and parsed structured output path in run artifacts.

Recommended argv shape:

```text
claude --bare --print "$PROMPT" --output-format json --json-schema "$SCHEMA_JSON" --tools "" --model "$MODEL" --max-turns 1
```

### 8.3 Ollama

Ollama remains a local work-proposal provider.

Ollama does not score work proposals in v0.2.

Ollama outputs may use JSON extraction because local Ollama behavior is not
schema-native in the same way as Codex and Claude Code.

---

## 9. Cross-Scoring Protocol

The v0.2 protocol is:

1. Generate proposals from enabled work providers.
2. Validate proposals against schema.
3. Mechanically validate proposal patches.
4. For each valid proposal, score it with every enabled scoring provider except
   its authoring provider.
5. A provider's self-score may be recorded only as diagnostic metadata, never as
   quorum evidence.
6. Build an explicit score matrix with:
   - `proposal_id`
   - `author_provider`
   - `scorer_provider`
   - `score`
   - `valid`
   - `rationale`
   - `required_fixes`
   - `risks`
   - `schema_validation`
7. Compute:
   - `cross_score_count`
   - `score_mean`
   - `score_spread`
   - `frontier_score_gap`
   - `disagreement_flags`
   - `quorum_result`
8. Select only if quorum passes.
9. Otherwise write `review.md` and `manifest.json` with
   `human_review_required`.

---

## 10. Quorum Policy

A valid automated selection requires:

- at least one valid work proposal;
- at least one valid cross-score from a different frontier provider;
- no hard validation failures on the selected patch;
- no critical disagreement flag unless manually overridden.

Default thresholds:

```text
frontier_score_gap >= 25 => critical disagreement / human review required
selected_score < 70 => human review required
selected patch validation failure => no automated selection
no valid cross-score from a different frontier provider => no automated selection
```

Manual override is not implemented in v0.2.

Self-scores must be excluded from quorum evidence.

---

## 11. Run Artifacts

Run directories must include the v0.1 artifacts plus v0.2 artifacts:

```text
runs/<run-id>/
  manifest.json
  snapshot/
  schemas/
  prompts/
    codex_work_prompt.md
    claude_work_prompt.md
    ollama_work_prompt.md
    <provider>_score_<proposal>.md
  responses/
    codex_work_response.json
    codex_work_events.jsonl
    codex_work_stderr.txt
    claude_work_stdout.json
    claude_work_stderr.txt
    claude_work_structured_output.json
    claude_work_attempt.json
    <provider>_score_<proposal>_response.json
    <provider>_score_<proposal>_stdout.json
    <provider>_score_<proposal>_stderr.txt
    <provider>_score_<proposal>_attempt.json
  parsed/
    codex_work_proposal.json
    claude_work_proposal.json
    ollama_<safe_model_name>_proposal.json
    score_matrix.json
    score_aggregates.json
    score_result.json
  patches/
    codex.patch
    claude.patch
    ollama_<safe_model_name>.patch
    selected.patch
  review.md
  commit_message.txt
```

`selected.patch` and `commit_message.txt` are written only when quorum passes.

---

## 12. Manifest Requirements

`manifest.json` must include:

- `schema_version`
- `providers_attempted`
- `providers_succeeded`
- `providers_failed`
- `provider_attempts`
- `provider_successes`
- `provider_failures`
- `score_matrix`
- `score_aggregates`
- `cross_score_count`
- `score_mean`
- `score_spread`
- `frontier_score_gap`
- `disagreement_flags`
- `quorum_result`
- `selected_proposal_id`
- `automated_selection_valid`
- `human_review_required`
- `artifact_publication_status`

`artifact_publication_status` is `operator_pending` after `review.md` is
written. `model-committee` must not automatically copy, commit, or push
artifacts to `../model-committee-artifacts`.

---

## 13. `review.md` Requirements

Generated `review.md` must:

- surface provider attempts and successes;
- surface the cross-score matrix;
- surface disagreement flags prominently;
- state whether automated selection is valid or blocked;
- state whether human review is required;
- include selected summary and validation details when a candidate exists;
- include final operator-run artifact publication commands.

The artifact publication section must use this shape:

```bash
RUN_ID="<actual run id>"

mkdir -p ../model-committee-artifacts/runs
cp -r "$(pwd)/runs/${RUN_ID}" ../model-committee-artifacts/runs/

git -C ../model-committee-artifacts add "runs/${RUN_ID}"
git -C ../model-committee-artifacts commit -S -m "UMC artifact ${RUN_ID}"
git -C ../model-committee-artifacts push
```

These commands are documentation for the operator only. They must not be
executed automatically.

---

## 14. Doctor Requirements

`doctor` must check:

- Python version is `>= 3.12`;
- `git` is available;
- Codex CLI availability and required flags;
- Claude Code availability;
- Claude Code version is at least `2.1.146`;
- Claude Code auth status;
- Claude Code `--json-schema` support;
- Claude Code schema-native smoke test when configured as safe and cheap;
- Ollama local reachability;
- configured Ollama model installation warnings;
- required target repo files;
- runs directory writability.

`doctor` should warn, but not fail, when optional smoke tests are disabled.

---

## 15. Patch Validation

Patch validation remains v0.1-compatible.

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

`work-select` must not apply patches.

---

## 16. Test Commands

Required validation commands:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
