from model_committee.patches.extract import enforce_allowed_patch_files
from model_committee.patches.validate import validate_patch


VALID_PATCH = """diff --git a/DESIGN.md b/DESIGN.md
index d2a4c9f..19eb29d 100644
--- a/DESIGN.md
+++ b/DESIGN.md
@@ -1,4 +1,4 @@
 # Design
 
-Original design line.
+Selected design line.
 
"""


def test_patch_allowlist():
    assert enforce_allowed_patch_files(VALID_PATCH) == ["DESIGN.md"]


def test_patch_validation_applies(git_fixture_repo):
    result = validate_patch(git_fixture_repo, "proposal", VALID_PATCH)
    assert result.patch_applies is True
    assert result.allowlist_passed is True


def test_patch_validation_rejects_forbidden_file(git_fixture_repo):
    patch = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
    result = validate_patch(git_fixture_repo, "proposal", patch)
    assert result.allowlist_passed is False
