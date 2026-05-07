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

