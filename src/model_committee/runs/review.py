from pathlib import Path

from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import WorkProposal
from model_committee.runs.manifest import RunManifest


def write_review(
    run_dir: Path,
    manifest: RunManifest,
    proposals: dict[str, WorkProposal],
    validations: dict[str, PatchValidationResult],
) -> None:
    selected = proposals.get(manifest.selected_proposal_id or "")
    selected_validation = validations.get(manifest.selected_proposal_id or "")
    text = f"""# Model-Committee Review

Run: `{manifest.run_id}`  
Question: `{manifest.selected_question_id}`  
Base commit: `{manifest.base_commit}`  
Automated selection: {"valid" if manifest.automated_selection_valid else "blocked"}
Human review required: {"yes" if manifest.human_review_required else "no"}
Selected proposal: `{manifest.selected_proposal_id or "none"}`

## Disagreement Flags

"""
    text += _format_flags(manifest)
    text += """
## Quorum Result

"""
    if manifest.quorum_result:
        result = manifest.quorum_result
        text += f"""- Valid automated selection: {"yes" if result.valid else "no"}
- Selected score: {result.selected_score if result.selected_score is not None else "n/a"}
- Selected cross-score count: {result.selected_cross_score_count}
- Blocked reasons: {_comma_or_none(result.blocked_reasons)}
"""
    else:
        text += "No quorum result recorded.\n"

    text += """
## Provider Attempts

| Phase | Provider | Model | Target proposal |
| --- | --- | --- | --- |
"""
    if manifest.provider_attempts:
        for attempt in manifest.provider_attempts:
            text += (
                f"| `{attempt.phase}` | `{attempt.provider_id}` | "
                f"`{attempt.model_name or 'n/a'}` | "
                f"`{attempt.target_proposal_id or 'n/a'}` |\n"
            )
    else:
        text += "| n/a | n/a | n/a | n/a |\n"

    text += """
## Provider Successes

| Phase | Provider | Model | Target proposal |
| --- | --- | --- | --- |
"""
    if manifest.provider_successes:
        for success in manifest.provider_successes:
            text += (
                f"| `{success.phase}` | `{success.provider_id}` | "
                f"`{success.model_name or 'n/a'}` | "
                f"`{success.target_proposal_id or 'n/a'}` |\n"
            )
    else:
        text += "| n/a | n/a | n/a | n/a |\n"

    text += """
## Cross-Score Matrix

| Proposal | Author | Scorer | Valid | Score | Rationale | Required fixes | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- |
"""
    if manifest.score_matrix:
        for row in manifest.score_matrix:
            text += (
                f"| `{row.proposal_id}` | `{row.author_provider}` | `{row.scorer_provider}` | "
                f"{'yes' if row.valid else 'no'} | "
                f"{row.score if row.score is not None else 'n/a'} | "
                f"{_cell(row.rationale or row.schema_validation.message or '')} | "
                f"{_cell(_comma_or_none(row.required_fixes))} | "
                f"{_cell(_comma_or_none(row.risks))} |\n"
            )
    else:
        text += "| n/a | n/a | n/a | no | n/a | no score rows | None | None |\n"

    if selected:
        text += f"""
## Selected Summary

{selected.summary}

## Changed Files

"""
        text += "".join(f"- `{path}`\n" for path in selected.changed_files)
        if selected_validation:
            text += f"""
## Validation

- Patch applies: {"yes" if selected_validation.patch_applies else "no"}
- Patch allowlist passed: {"yes" if selected_validation.allowlist_passed else "no"}
- Question schema preserved: {"yes" if not selected.validation_notes else "review required"}
"""
        text += """
## Risks

"""
        risks = sorted({risk for row in manifest.score_matrix for risk in row.risks})
        text += "None reported.\n" if not risks else "".join(f"- {risk}\n" for risk in risks)
    else:
        text += """
## Selected Summary

No proposal passed automated quorum.
"""

    text += """
## Next Manual Steps

"""
    if manifest.automated_selection_valid:
        text += f"""```bash
git -C {manifest.repo_path} apply "$(pwd)/runs/{manifest.run_id}/patches/selected.patch"
git -C {manifest.repo_path} commit -S -F "$(pwd)/runs/{manifest.run_id}/commit_message.txt"
```
"""
    else:
        text += "Automated selection is blocked. Inspect the proposals and matrix before applying any patch.\n"

    text += f"""
## Artifact Publication

Operator-run only. Do not execute automatically from model-committee.

```bash
RUN_ID="{manifest.run_id}"

mkdir -p ../model-committee-artifacts/runs
cp -r "$(pwd)/runs/${{RUN_ID}}" ../model-committee-artifacts/runs/

git -C ../model-committee-artifacts add "runs/${{RUN_ID}}"
git -C ../model-committee-artifacts commit -S -m "UMC artifact ${{RUN_ID}}"
git -C ../model-committee-artifacts push
```
"""
    (run_dir / "review.md").write_text(text, encoding="utf-8")


def _format_flags(manifest: RunManifest) -> str:
    if not manifest.disagreement_flags:
        return "None.\n"
    lines = []
    for flag in manifest.disagreement_flags:
        lines.append(
            f"- **{flag.severity.upper()}** `{flag.code}`"
            f"{f' on `{flag.proposal_id}`' if flag.proposal_id else ''}: {flag.message}"
        )
    return "\n".join(lines) + "\n"


def _comma_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
