# Prompt Context Plan — dependency-closure filtering (v0.4)

Status: Proposed
Created: 2026-09-16
Applies to: `model-committee` v0.3.0 → v0.4

## 1. Problem

`render_work_prompt` (`src/model_committee/prompts/work_prompt.py:14-19`) embeds four
canonical files in full on every run. Against the `ubu-design` repo that is:

| File | chars | ~tokens |
|---|---|---|
| DESIGN.md | 334,991 | 83,747 |
| DECISIONS.md | 229,338 | 57,334 |
| OPEN_QUESTIONS.md | 181,389 | 45,347 |
| PLANNING_KERNEL_CONTRACT.md | 23,423 | 5,855 |
| **payload** | **769,141** | **192,285** |

`PROMPT_SIZE_WARNING_LIMIT` is 100,000 chars, so the prompt is ~7.7x the limit.

Prose compression has already been taken to its floor (2026-09-15: 60 Phase 1 decisions
tombstoned against their `→ DESIGN.md §N` pointers, 12 Solved questions tombstoned,
−178,287 chars / −18.8%). What remains is not redundant: 335k of canonical design, 229k
of live decisions, 181k of open questions. Measured duplication across the whole corpus
is under 4k chars. **The budget cannot be closed by editing prose.**

## 2. Approach

Send only the context the selected question actually needs, resolved by following the
reference graph the corpus already maintains.

Closure for a selected question Q:

1. Q itself, plus the transitive closure of `Depends on:`.
2. Decisions named in those questions' `Resolved by:`, plus any `UBU-Dxxxx` cited in
   their bodies (one hop).
3. Sections named by `§`/`§§` references in any of the above.
4. A small always-include core for cross-cutting invariants that nothing links to.

### Measured closure sizes (19 Phase 1b questions)

| | closure chars | with 5,835 fixed overhead | vs limit |
|---|---|---|---|
| best (`UBU-Q0140`) | 4,394 | 10,229 | 0.10x |
| mean | 17,428 | 23,263 | 0.23x |
| worst (`UBU-Q0137`) | 70,029 | 75,864 | 0.76x |
| today (4 whole files) | 767,846 | 773,681 | 7.74x |

Every Phase 1b question fits under `PROMPT_SIZE_WARNING_LIMIT`, with room to add the
sync contract as a fifth source.

### Verified: excerpts do not break patching

Patches are validated by `git apply` against a copy of the full repo
(`patches/validate.py:_create_temp_validation_repo`), so a model that saw only excerpts
must still produce a diff that applies to whole files.

Tested 2026-09-16: a hunk header claiming `@@ -10,3 +10,4 @@` whose context lines
actually occur at line 150 applied cleanly, both plain and with `--recount`. `git apply`
locates hunks by context and tolerates offsets. **Models need correct context lines, not
correct line numbers.** Excerpt-based prompting is compatible with the existing
validation path.

## 3. Why ID closure is sufficient (and the vocabulary backstop was wrong)

An earlier draft proposed a term-matching backstop: index `**(net-new)**` vocabulary and
pull in defining sections for terms appearing in the question. That was a heuristic patch
over missing data. Rejected.

The real defect is the reference graph, and it is repairable:

- `UBU-Q0130` asks about `observed_versions`, `effective_time`, `recorded_time`,
  `derived_state`, and `SyncStatement`.
- All five are defined **only** in `DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md`
  (`SyncStatement` §188, `derived_state` table §468, envelopes §366/§626), and appear
  **zero** times in `DESIGN.md`.
- Across the entire corpus there are 13 inbound section references to that contract.
  Twelve are the `§28` "Formerly UBU-QSYNC-NNN" provenance lines added during the
  2026-09-15 migration, and §28 is now a redirect stub. Exactly one (`UBU-D0226`,
  `DECISIONS.md:3493`) points at real content.

So the closure fails for these questions because nothing points at the right sections —
not because closure is the wrong method. The corpus already proves the method works: 189
decisions carry `→ DESIGN.md §N` and resolve correctly.

Repairing the twelve edges is better than a heuristic on every axis: auditable (you can
see why a section was included), consistent with existing convention, no silent over- or
under-pull, human-correctable, and independent of whether `(net-new)` markers stay
maintained.

Its one weakness — a question with a missing pointer silently gets thin context — is
handled by making it loud (step 6: warn on thin closure).

## 4. Steps

### Step 1 — add `DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md` to the prompt files

Read-only fifth source. **Not** added to `ALLOWED_PATCH_FILES`: models may reason about
it but not propose changes to it. Extending committee write authority to a fifth
canonical file is a governance change against `UBU-D0176` and is out of scope here.

- `constants.py`: `REQUIRED_REPO_FILES`
- `prompts/work_prompt.py`: new read + format arg
- `prompts/work_prompt.md`: new `{device_sync_contract_md}` placeholder
- `runs/layout.py`: `create_run_dir` snapshot loop follows `REQUIRED_REPO_FILES`
- 9 test fixtures under `tests/fixtures/` need the new file

Interim cost: +55,527 chars, taking the payload to ~8.2x the limit. Steps 4-5 reverse
this. Accepted because answering schema questions without the schema is worse than an
oversized prompt.

### Step 2 — remove the hygiene rules

Delete `prompts/work_prompt.md:53-75` (all three subsections: "Tombstone solved
questions", "Remove duplicate information", "Compress to effective minimum") and update
`IMPLEMENTATION_CONTRACT.md:31`, which documents them.

All three require whole-corpus visibility to execute safely. Under excerpts, "remove
duplicate information" would instruct a model to delete content whose other copy it
cannot see.

Consequence: nothing will instruct tombstoning of solved questions any more. That rule
was also corpus hygiene, not only prompt economy — its absence is why 12 un-tombstoned
Solved questions accumulated. Under closure filtering this no longer costs prompt budget.
If the behaviour is wanted, its correct home is a `check` warning ("Solved question still
carries a full body"), where the whole file is actually visible — not a prompt
instruction.

### Step 3 — repair the reference graph

Status: **done 2026-09-16.**

Each question carries a `Defining context: <file> §§...` line after its metadata line
(after it, never before — the parser takes the first non-blank line after the heading as
the metadata record). Data change, not code. Mappings verified against section content,
not titles:

| Question | Subject | Sections |
|---|---|---|
| UBU-Q0130 | mutation envelope metadata | §4, §8, §9, §15 |
| UBU-Q0139 | sync topology | §3, §25, §26 |
| UBU-Q0140 | causality / ordering | §8, §15 |
| UBU-Q0141 | encrypted indirect transport | §8, §27 |
| UBU-Q0142 | mid-session disconnect | §16, §17 |
| UBU-Q0143 | conflict classes | §16, §17 |
| UBU-Q0144 | deletion on offline Devices | §12, §18 |
| UBU-Q0145 | worker Device protocol | §20 |
| UBU-Q0146 | sync-state warnings | §23 |
| UBU-Q0147 | manual-review Task regress | §17 |
| UBU-Q0148 | Device / enclave identity | §4, §5 |
| UBU-Q0149 | token custody | §21 |
| UBU-Q0150 | redacted handle stability | §10, §12 |

Two mappings guessed from section titles were wrong and were corrected by reading the
content: Q0142 is §16/§17 (`incomplete_sync_session` at line 701, checkpoint semantics at
731), not §13/§14; Q0144 is §12/§18, not §18/§19.

Scope was wider than "the twelve migrated questions". `UBU-Q0130` is an original Phase 1b
question that references sync-only vocabulary directly and also needed an edge. It was
the only one of `UBU-Q0130`-`UBU-Q0136` that did — verified by extracting backticked
terms present in the sync contract but absent from `DESIGN.md`.

Verified: the `UBU-Q0130` closure (itself + `Q0131`, `Q0140`, `Q0148` via `Depends on:`)
now pulls §4, §5, §8, §9, §15 — 10,137 chars, covering all five terms the question asks
about (`SyncStatement`, `observed_versions`, `recorded_time`, `effective_time`,
`derived_state`), against 55,527 for the whole file. An 82% reduction with full
vocabulary coverage.

Note for step 4: §4 "Core definitions" (1,519 chars) is foundational vocabulary that many
questions need and nothing naturally links to. It belongs in the always-include core
rather than being repeated on individual questions.

### Step 4 — context-selection module

Status: **done 2026-09-16.** `src/model_committee/context/` (`index.py`, `closure.py`),
14 tests in `tests/test_context_closure.py`. `work_prompt.py` is untouched; wiring is
step 5.

Measured over the 19 Phase 1b questions, closure + 5,835 fixed overhead:

| | vs `PROMPT_SIZE_WARNING_LIMIT` |
|---|---|
| today, four whole files | 7.75x |
| mean closure | **0.40x** |
| best (`UBU-Q0145`) | 0.11x |
| worst (`UBU-Q0137`) | **1.42x — still over** |

**Correction to this plan's earlier estimate.** The first prototype reported a 0.76x worst
case and a 0.23x mean. That prototype sliced a section as "heading to next heading of any
level", so `§16` meant only the prose before `§16.1`. Correct nested-inclusive slicing
makes referenced sections substantially larger, and the honest numbers are the ones above.
The mean still improves ~19x; the worst case does not fit.

`UBU-Q0137` is over because two coarse top-level references dominate it: `DESIGN.md §3`
(31,033 chars) and `§16` (30,280) are 61,313 of its 98,494 section chars. Its 17 questions
and 15 decisions contribute only 39,915 between them. Options, none taken yet:

- cap an oversized section to its intro plus subsection headings;
- prefer the most specific reference when a decision cites a whole chapter;
- accept it — `prompt_size_warning` fires, which is the warning working correctly, and
  1.42x is still a 5.5x improvement on today for the worst case.

Two defects found and fixed while building:

- **Overlapping sections.** `§3` is nested-inclusive so it already contains `§3.1`;
  selecting both emitted the text twice and double-counted the size.
  `_drop_descendants` keeps the ancestor. This was a correctness bug, not only size.
- **The retired `§28` stub resolved as a live reference.** The `Formerly UBU-QSYNC-NNN
  (... §28, retired)` provenance lines added in step 3 were file-qualified references, so
  every migrated question pulled in the redirect table. The provenance lines now read
  `(retired from <file> section 28)` — readable to a human, inert to the resolver.

Design decisions worth keeping:

- **Only file-qualified references resolve.** A bare `§15` is ambiguous across sources and
  is ignored rather than guessed at. The corpus already writes references file-qualified.
- **Unresolvable references are recorded**, not dropped silently — `ClosureResult.
  missing_refs` feeds step 6's warning.
- **Always-include core is `DESIGN.md §1` + sync `§4`** (~4.2k), set in
  `ALWAYS_INCLUDE_SECTIONS`. `DESIGN.md §2` "Core Principles" was the obvious candidate
  for cross-cutting invariants but is 32,198 chars nested-inclusive — it would dominate
  the mean closure, so it is left to explicit references.

### Step 4 (original sketch)

New package `src/model_committee/context/`:

- Indexes: `DESIGN.md` and `PLANNING_KERNEL_CONTRACT.md` by dotted section number,
  `DECISIONS.md` by `UBU-D` id, `OPEN_QUESTIONS.md` by `UBU-Q` id, sync contract by
  section. `DESIGN.md` is hierarchically numbered (32 `##`, 177 `###`, 18 `####`), so
  `§4.1` / `§23.6` map onto headings directly.
- `compute_closure(question_id) -> ClosureResult` with the ids and sections selected.
- Always-include core for cross-cutting invariants (principles sections; ~10-15k chars,
  comfortably within budget).
- Tests pinning closure determinism.

### Step 5 — renderer, template, framing

- `work_prompt.py` renders excerpts instead of whole files.
- Template: excerpt sections replace the fixed per-file placeholders. Note
  `render_work_prompt` uses `str.format`, so any literal `{` added to the template must
  be doubled or rendering raises `KeyError`.
- **Excerpt framing** — state explicitly that these are excerpts and that ids not shown
  still exist. Without it a model reads absence as non-existence and re-decides settled
  questions.
- **Injected next-free ids** — `next free: UBU-Q0151 / UBU-D0246`. Models allocate new
  ids for added questions and decisions; without the full file they will collide.

### Step 6 — manifest and checker

- Persist the selected ids/sections in the run manifest so a run is explainable and
  reproducible. Bump `manifest.schema_version` `"0.3"` → `"0.4"`.
- `create_run_dir` keeps snapshotting full files for audit.
- `checker.py:74-99`: `DECISIONS_PROMPT_BUDGET_WARNING` / `_HARD_WARNING` measure
  whole-file size, which no longer drives the prompt. Re-base on rendered prompt size or
  remove. This retires the standing hard warning by making it measure the right thing.
- New warning: thin closure (below a threshold, or a question citing a file without a
  section) — makes missing graph edges visible rather than silent.

### Step 7 — record the architecture change

New `UBU-D` in `ubu-design/DECISIONS.md`, in the style of `UBU-D0150`, recording:

- the committee no longer sees whole canonical files;
- the sync contract joins as a read-only fifth source;
- the hygiene rules are withdrawn, and why;
- closure completeness now depends on section pointers being maintained.

Plus `IMPLEMENTATION_CONTRACT.md` bump to v0.4.

## 5. Risks

- **Wrong or missing edges yield wrong context.** Mitigated by step 6's thin-closure
  warning and human review of step 3's edges.
- **Cross-cutting invariants** ("eject-not-override", compartment rules) are linked by no
  id and could drop out. Mitigated by step 4's always-include core.
- **Over-filtering** reduces incidental awareness that a whole-file prompt gave for free.
  No mitigation beyond the always-include core; accept and observe.
- **Step 1 temporarily makes the prompt larger** before steps 4-5 make it much smaller.

## 6. Notes

- Test baseline at time of writing: 47 passed, 9 errors. The 9 are environmental —
  `commit.gpgsign=true` is set globally and `tests/test_patch_validate.py` commits
  without a signing key. Unrelated to this work; fixable with
  `-c commit.gpgsign=false` in the test helper.
