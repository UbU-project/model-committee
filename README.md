# model-committee

Bootstrap model committee automation for the UbU project.

This repository implements the narrow v0.4 contract in `IMPLEMENTATION_CONTRACT.md`.

Status: active pre-MVP dogfooding bootstrap for the canonical `ubu-design` repo.

Authority: committee output is advisory. Invoking `uber-loop` opts into applying and
committing selected proposals to the design repository.

License: MPL-2.0.

```bash
uv sync
uv run model-committee doctor --repo ../ubu-design
uv run model-committee run-loop --repo ../ubu-design --config config/models.json --phase "Phase 2"
```

To continuously apply selected proposals and publish their artifacts:

```bash
uv run model-committee uber-loop --repo ../ubu-design --config config/models.json --phase "Phase 2"
```

`uber-loop` accepts every `run-loop` option. Each iteration runs `run-loop` with
the same options, applies the returned run's `selected.patch`, stages its changed
files, and creates a signed design commit using `commit_message.txt`. It then
copies that exact run, including a custom `--runs-dir`, to
`../model-committee-artifacts/runs/<run-id>`, creates a signed artifact commit, and
pushes the artifact repository before repeating. The artifact repository path is
relative to the current working directory.

Each invocation works through eligible questions in ranking order before revisiting
an incomplete question. If every currently eligible question has been worked on,
the next pass starts with the highest-ranked question still eligible. This rotation
is kept in memory and resets when `uber-loop` restarts. Questions marked
`Human approval required` continue through the existing automated-selection checks.

Configure Git signing in both repositories and an existing artifact repository
with a push remote. Both indexes must be empty before each iteration; unstaged
edits are allowed. Staging a selected patch's file also includes existing edits
in that file. Ranking changes to `OPEN_QUESTIONS.md` remain unstaged unless the
selected patch changes that file. An existing artifact run directory stops the
command before patch application.

The loop stops at the first failure, including no eligible question, or on
Ctrl-C (exit code 8). Completed commits and copied artifacts are retained after
a later failure. Other commands continue to leave application and publication
to the operator.
