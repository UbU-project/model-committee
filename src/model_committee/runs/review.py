from pathlib import Path

from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import ScoreResult, WorkProposal
from model_committee.runs.manifest import RunManifest


def write_review(
    run_dir: Path,
    manifest: RunManifest,
    proposal: WorkProposal,
    score_result: ScoreResult,
    validation: PatchValidationResult,
) -> None:
    risks = []
    score = next(
        (item for item in score_result.scores if item.proposal_id == proposal.proposal_id), None
    )
    if score:
        risks = score.risks
    text = f"""# Model-Committee Review

Run: `{manifest.run_id}`  
Question: `{manifest.selected_question_id}`  
Base commit: `{manifest.base_commit}`  
Selected proposal: `{proposal.proposal_id}`

## Selected summary

{proposal.summary}

## Selection rationale

{score_result.selection_rationale}

## Changed files

"""
    text += "".join(f"- `{path}`\n" for path in proposal.changed_files)
    text += f"""
## Validation

- Patch applies: {"yes" if validation.patch_applies else "no"}
- Patch allowlist passed: {"yes" if validation.allowlist_passed else "no"}
- Question schema preserved: {"yes" if not proposal.validation_notes else "review required"}

## Risks

"""
    text += "None reported.\n" if not risks else "".join(f"- {risk}\n" for risk in risks)
    text += f"""
## Next manual steps

```bash
git -C {manifest.repo_path} apply "$(pwd)/{run_dir}/patches/selected.patch"
git -C {manifest.repo_path} commit -F "$(pwd)/{run_dir}/commit_message.txt"
```
"""
    (run_dir / "review.md").write_text(text, encoding="utf-8")
