from model_committee.constants import ALLOWED_PATCH_FILES
from model_committee.responses.schema_files import WORK_PROPOSAL_SCHEMA


def test_work_proposal_schema_changed_files_matches_patch_allowlist():
    enum = WORK_PROPOSAL_SCHEMA["properties"]["changed_files"]["items"]["enum"]
    assert enum == sorted(ALLOWED_PATCH_FILES)
    assert "PLANNING_KERNEL_CONTRACT.md" in enum
