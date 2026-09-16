import re
from pathlib import Path

from pydantic import BaseModel

SECTION_HEADING_RE = re.compile(r"^(#{2,6})\s+(?:([\d]+(?:\.[\d]+)*)\.?\s+)?(.+?)\s*$")
ID_HEADING_RE = re.compile(r"^##\s+(UBU-[DQ][0-9]{4})(?::|\s+—)\s+(.+?)\s*$")

# `DESIGN.md §4.1`, `DESIGN.md §§15.2.2, 16`, `SYNC.md §4, §8, §9`
FILE_REF_RE = re.compile(r"([A-Z][A-Z0-9_]*\.md)\s*(§§?[\d.]+(?:\s*,\s*§?\s*[\d.]+)*)")
SECTION_NUM_RE = re.compile(r"[\d]+(?:\.[\d]+)*")


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class Section(BaseModel):
    key: str
    title: str
    level: int
    text: str


class SectionIndex(BaseModel):
    """Markdown sections keyed by dotted number, and by title slug when unnumbered.

    A section's text runs to the next heading of the same or higher level, so `§23`
    includes `§23.1`..`§23.6` rather than only the text before the first subsection.
    """

    filename: str
    sections: dict[str, Section]

    @classmethod
    def from_text(cls, filename: str, text: str) -> "SectionIndex":
        lines = text.split("\n")
        heads: list[tuple[int, int, str | None, str]] = []
        for i, line in enumerate(lines):
            match = SECTION_HEADING_RE.match(line)
            if match and not ID_HEADING_RE.match(line):
                heads.append((i, len(match.group(1)), match.group(2), match.group(3)))

        sections: dict[str, Section] = {}
        for pos, (start, level, number, title) in enumerate(heads):
            end = len(lines)
            for other_start, other_level, _, _ in heads[pos + 1 :]:
                if other_level <= level:
                    end = other_start
                    break
            key = number if number else slugify(title)
            if key and key not in sections:
                sections[key] = Section(
                    key=key, title=title, level=level, text="\n".join(lines[start:end])
                )
        return cls(filename=filename, sections=sections)

    @classmethod
    def from_file(cls, path: Path) -> "SectionIndex":
        return cls.from_text(path.name, path.read_text(encoding="utf-8"))

    def get(self, key: str) -> Section | None:
        return self.sections.get(key)


class Entry(BaseModel):
    entry_id: str
    title: str
    text: str


class IdIndex(BaseModel):
    """`UBU-Dxxxx` / `UBU-Qxxxx` blocks keyed by id."""

    filename: str
    entries: dict[str, Entry]

    @classmethod
    def from_text(cls, filename: str, text: str) -> "IdIndex":
        lines = text.split("\n")
        heads = [
            (i, match.group(1), match.group(2))
            for i, line in enumerate(lines)
            if (match := ID_HEADING_RE.match(line))
        ]
        entries: dict[str, Entry] = {}
        for pos, (start, entry_id, title) in enumerate(heads):
            end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
            entries.setdefault(
                entry_id, Entry(entry_id=entry_id, title=title, text="\n".join(lines[start:end]))
            )
        return cls(filename=filename, entries=entries)

    @classmethod
    def from_file(cls, path: Path) -> "IdIndex":
        return cls.from_text(path.name, path.read_text(encoding="utf-8"))


def find_section_refs(text: str) -> dict[str, set[str]]:
    """Return {filename: {section keys}} for file-qualified section references.

    Only file-qualified references are resolved. A bare `§15` is ambiguous across
    source files, so it is ignored rather than guessed at.
    """
    refs: dict[str, set[str]] = {}
    for filename, run in FILE_REF_RE.findall(text):
        numbers = set(SECTION_NUM_RE.findall(run))
        if numbers:
            refs.setdefault(filename, set()).update(numbers)
    return refs
