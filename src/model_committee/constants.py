from pathlib import Path

VERSION = "0.4.0"
DEFAULT_CONFIG_PATH = Path("config/models.json")
DEFAULT_RUNS_DIR = Path("runs")
REQUIRED_REPO_FILES = (
    "DESIGN.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "PLANNING_KERNEL_CONTRACT.md",
    "DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md",
)
ALLOWED_PATCH_FILES = {
    "DESIGN.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "PLANNING_KERNEL_CONTRACT.md",
}
DESIGN_FILE = "DESIGN.md"
DECISIONS_FILE = "DECISIONS.md"
OPEN_QUESTIONS_FILE = "OPEN_QUESTIONS.md"
PLANNING_KERNEL_CONTRACT_FILE = "PLANNING_KERNEL_CONTRACT.md"
DEVICE_SYNC_CONTRACT_FILE = "DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md"

# Files sliced by section for dependency-closure context selection.
SECTION_SOURCE_FILES = (
    DESIGN_FILE,
    PLANNING_KERNEL_CONTRACT_FILE,
    DEVICE_SYNC_CONTRACT_FILE,
)

# Cross-cutting context that nothing in the reference graph links to, so closure
# would never reach it. Kept small: it is paid on every run.
ALWAYS_INCLUDE_SECTIONS = {
    DESIGN_FILE: ("1",),  # Overview
    DEVICE_SYNC_CONTRACT_FILE: ("4",),  # Core definitions (Device, SyncStatement, ...)
}

PROMPT_SIZE_WARNING_LIMIT = 100_000
ESTIMATED_CHARS_PER_TOKEN = 4

# Fixed prompt cost outside the closure: template plus JSON schema. Used to warn when a
# question's context will not fit, before a run is attempted.
PROMPT_FIXED_OVERHEAD_CHARS = 6_000

EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONSISTENCY_FAILURE = 2
EXIT_PROVIDER_FAILURE = 3
EXIT_INVALID_MODEL_OUTPUT = 4
EXIT_NO_VALID_PATCH_PROPOSALS = 5
EXIT_PATCH_VALIDATION_FAILED = 6
EXIT_NO_ACCEPTABLE_SELECTION = 7
EXIT_USER_CANCELED = 8
EXIT_HUMAN_REVIEW_REQUIRED = 9
