import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from model_committee.constants import (
    ALWAYS_INCLUDE_SECTIONS,
    DECISIONS_FILE,
    OPEN_QUESTIONS_FILE,
    SECTION_SOURCE_FILES,
)
from model_committee.context.index import IdIndex, SectionIndex, find_section_refs

DECISION_ID_RE = re.compile(r"UBU-D[0-9]{4}")


class ClosureResult(BaseModel):
    """What context a selected question needs, and why it was selected."""

    question_id: str
    question_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    sections: dict[str, list[str]] = Field(default_factory=dict)
    core_sections: dict[str, list[str]] = Field(default_factory=dict)
    missing_refs: dict[str, list[str]] = Field(default_factory=dict)
    total_chars: int = 0


class RepoContext(BaseModel):
    """Parsed indexes for one repo. Built once, reused across closures."""

    questions: IdIndex
    decisions: IdIndex
    sections: dict[str, SectionIndex]

    @classmethod
    def load(cls, repo: Path) -> "RepoContext":
        repo = Path(repo)
        return cls(
            questions=IdIndex.from_file(repo / OPEN_QUESTIONS_FILE),
            decisions=IdIndex.from_file(repo / DECISIONS_FILE),
            sections={name: SectionIndex.from_file(repo / name) for name in SECTION_SOURCE_FILES},
        )


def _dependencies(text: str) -> list[str]:
    match = re.search(r"Depends on: (.+?) Blocks:", text)
    if not match or match.group(1).strip() in {"None", "TBD", "Unresolved", "Never"}:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def _resolved_by(text: str) -> list[str]:
    match = re.search(r"Resolved by: (.+?) Last scored:", text)
    if not match:
        return []
    return DECISION_ID_RE.findall(match.group(1))


def compute_closure(context: RepoContext, question_id: str) -> ClosureResult:
    """Select the context a question needs by following the corpus reference graph.

    1. the question, plus the transitive closure of `Depends on:`
    2. decisions named in those questions' `Resolved by:`, plus decisions cited in
       their bodies (one hop)
    3. sections named by file-qualified `§` references in any of the above
    4. the always-include core
    """
    seen: set[str] = set()
    stack = [question_id]
    while stack:
        current = stack.pop()
        if current in seen or current not in context.questions.entries:
            continue
        seen.add(current)
        stack.extend(_dependencies(context.questions.entries[current].text))

    question_text = "".join(context.questions.entries[q].text for q in sorted(seen))

    decision_ids: set[str] = set()
    for qid in seen:
        decision_ids.update(_resolved_by(context.questions.entries[qid].text))
    decision_ids.update(DECISION_ID_RE.findall(question_text))
    decision_ids &= set(context.decisions.entries)
    decision_text = "".join(context.decisions.entries[d].text for d in sorted(decision_ids))

    refs = find_section_refs(question_text + decision_text)
    selected: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for filename, keys in refs.items():
        index = context.sections.get(filename)
        if index is None:
            continue
        found = sorted(_drop_descendants(k for k in keys if index.get(k)), key=_section_sort_key)
        absent = sorted((k for k in keys if not index.get(k)), key=_section_sort_key)
        if found:
            selected[filename] = found
        if absent:
            missing[filename] = absent

    core: dict[str, list[str]] = {}
    for filename, keys in ALWAYS_INCLUDE_SECTIONS.items():
        index = context.sections.get(filename)
        if index is None:
            continue
        chosen = selected.get(filename, [])
        present = [
            k
            for k in keys
            if index.get(k)
            and k not in chosen
            and not any(k.startswith(f"{other}.") for other in chosen)
        ]
        if present:
            core[filename] = present

    total = len(question_text) + len(decision_text)
    for group in (selected, core):
        for filename, keys in group.items():
            index = context.sections[filename]
            total += sum(len(section.text) for k in keys if (section := index.get(k)))

    return ClosureResult(
        question_id=question_id,
        question_ids=sorted(seen),
        decision_ids=sorted(decision_ids),
        sections=selected,
        core_sections=core,
        missing_refs=missing,
        total_chars=total,
    )


def _drop_descendants(keys: Iterable[str]) -> list[str]:
    """Drop sections already contained by a selected ancestor.

    Section text is nested-inclusive, so selecting both `§3` and `§3.1` would emit
    `§3.1` twice. The ancestor wins.
    """
    unique = set(keys)
    return [
        key
        for key in unique
        if not any(other != key and key.startswith(f"{other}.") for other in unique)
    ]


def _section_sort_key(key: str) -> tuple:
    try:
        return (0, tuple(int(part) for part in key.split(".")))
    except ValueError:
        return (1, key)
