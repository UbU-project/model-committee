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

### PLANNING_KERNEL_CONTRACT.md

```markdown
{planning_kernel_contract_md}
```

## JSON Schema

Your output must satisfy this schema:

```json
{work_proposal_schema}
```

## File hygiene requirements

Apply the following hygiene rules whenever they are relevant to the selected question. These are mandatory when applicable; do not skip them.

### Tombstone solved questions

When a question in `OPEN_QUESTIONS.md` is resolved by this proposal, convert its full block to a compact tombstone. A tombstone contains exactly:

1. The `## UBU-Qxxxx: Title` heading line (unchanged).
2. The single-line metadata record with `Status: Solved` and `Resolved by: UBU-Dxxxx` filled in.
3. A single resolution line: `Resolved. See UBU-Dxxxx.`
4. A horizontal rule: `---`

Remove all other prose, sub-sections (`### Background`, `### Options`, `### Current direction`, `### Resolution`), and blank lines between the metadata and the resolution line. The tombstone must parse without error under the existing metadata format.

### Remove duplicate information

When adding a decision to `DECISIONS.md` that supersedes or elaborates text already present in `DESIGN.md`, `DECISIONS.md`, or `OPEN_QUESTIONS.md`, remove or condense the superseded text. Do not add information that is already fully covered elsewhere in the canonical files.

### Compress to effective minimum

Write each new or updated section at the minimum length needed to convey the decision, constraint, or resolution unambiguously. Omit background narrative that is derivable from context or that repeats existing content. Prefer bullet lists over prose paragraphs for enumerated facts or field specifications.

## Requirements

- Return exactly one JSON object.
- Do not include hidden reasoning, `<think>` tags, markdown fences, or explanatory text outside the JSON object.
- All fields are required.
- Arrays may be empty.
- The patch must be a full git-diff-style patch.
- The patch may modify only:
  - `DESIGN.md`
  - `DECISIONS.md`
  - `OPEN_QUESTIONS.md`
  - `PLANNING_KERNEL_CONTRACT.md`
- Do not modify `README.md`, `OUTREACH.md`, hidden files, scripts, code files, or generated logs.
- Preserve the single-line metadata format in `OPEN_QUESTIONS.md`.
- The `patch` string must be a raw unified diff as produced by `git diff`; do not wrap it in markdown fences or prose.
- Every file diff must start with `diff --git a/<path> b/<path>`, followed by `--- a/<path>` and `+++ b/<path>`.
- Every hunk must include accurate `@@ -old_start,old_count +new_start,new_count @@` ranges and enough unchanged context for `git apply --check` to apply without `--recount`.
- When editing `OPEN_QUESTIONS.md`, anchor hunks with the selected question heading `## {question_id}: {question_title}` and its own `### Resolution` section. Do not use a repeated `### Resolution` heading from an earlier or later question as the edit location.
- If resolving the selected question, replace the `Unresolved.` text under that selected question's `### Resolution` section and update that same question's metadata line. Do not insert selected-question resolution text into any other question block.
- Use the existing `UBU-Qxxxx` and `UBU-Dxxxx` numbering conventions.
- Prefer minimal, auditable changesets.
- If the selected question is blocked, propose decomposition only if it produces replacement questions with fewer, simpler, or no dependencies.
- If the selected question is already partially resolved, narrow or clarify it rather than pretending it is fully unresolved.

Return only JSON.
