"""
knowledge.py
------------
Loads the curated notes in chatbot/knowledge/ as retrieval chunks for the "Ask the data" assistant.

Each note is a markdown file with one "# Title" line followed by "## Heading" sections. Every
section becomes one chunk, and its text starts with "<title> — <heading>", so a chunk that is
retrieved on its own still says what it is about. HTML comments are notes for maintainers and
are left out.
"""

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SECTION_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    id: str  # "<file stem>#<heading slug>", e.g. "counting_rules#team-medals-count-once"
    file: str  # e.g. "counting_rules.md"
    title: str
    heading: str
    text: str  # "<title> — <heading>\n<section body>"


def load_chunks(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    """Returns one chunk per "## " section of every .md file in directory, files in name order."""
    chunks = []
    for path in sorted(Path(directory).glob("*.md")):
        title, sections = _parse_note(path)
        for heading, body in sections:
            chunks.append(Chunk(
                id=f"{path.stem}#{_slug(heading)}",
                file=path.name,
                title=title,
                heading=heading,
                text=f"{title} — {heading}\n{body}",
            ))
    return chunks


def _parse_note(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Splits a note into its "# " title and its (heading, body) sections, without HTML comments."""
    text = _HTML_COMMENT.sub("", path.read_text(encoding="utf-8"))
    first_line, _, rest = text.strip().partition("\n")
    if not first_line.startswith("# "):
        raise ValueError(f"{path.name}: the first line must be a '# Title' line")
    preamble, *parts = _SECTION_HEADING.split(rest)
    if preamble.strip():
        raise ValueError(f"{path.name}: text between the title and the first '## ' section would never be retrieved")
    sections = [(heading.strip(), body.strip()) for heading, body in zip(parts[::2], parts[1::2])]
    return first_line[2:].strip(), sections


def _slug(heading: str) -> str:
    """'India's overall record' -> 'indias-overall-record'."""
    return re.sub(r"[^a-z0-9]+", "-", heading.lower().replace("'", "").replace("’", "")).strip("-")
