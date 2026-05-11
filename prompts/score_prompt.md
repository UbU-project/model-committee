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

## Provider weights

Use these static v0.1 trust weights as context when judging proposal quality. Do not use
raw one-provider-one-vote counting.

```json
{provider_weights_json}
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
