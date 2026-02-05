"""Discover and load Agent Skills from builtin and custom directories."""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A loaded agent skill with its name, description, and content."""

    name: str
    description: str
    content: str
    path: str
    source: str  # "builtin" or "custom"


def discover_skills(builtin_dir: str | None = None,
                    custom_dir: str | None = None) -> list[Skill]:
    """Discover and load skills from builtin and custom directories."""
    skills: list[Skill] = []

    # Built-in skills
    if builtin_dir is None:
        builtin_dir = str(
            Path(__file__).resolve().parent / "builtin"
        )

    if Path(builtin_dir).exists():
        for skill_dir in Path(builtin_dir).iterdir():
            if skill_dir.is_dir():
                skill = _load_skill(skill_dir, source="builtin")
                if skill:
                    skills.append(skill)

    # Custom skills
    if custom_dir and Path(custom_dir).exists():
        for skill_dir in Path(custom_dir).iterdir():
            if skill_dir.is_dir():
                skill = _load_skill(skill_dir, source="custom")
                if skill:
                    skills.append(skill)

    logger.info("Discovered %d skills: %s",
                len(skills), [s.name for s in skills])
    return skills


def _load_skill(skill_dir: Path, source: str) -> Skill | None:
    """Load a single skill from its directory, returning None if invalid."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return None

    content = skill_file.read_text(encoding="utf-8", errors="replace")
    name = skill_dir.name
    description = _extract_description(content)

    return Skill(
        name=name,
        description=description,
        content=content,
        path=str(skill_file),
        source=source,
    )


def _extract_description(content: str) -> str:
    """Extract the first descriptive line from skill content."""
    lines = content.strip().split("\n")

    # Try to find a description after the title
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped and not stripped.startswith("---"):
            # Take first non-empty, non-header line as description
            return stripped[:200]

    # Fall back to first line
    return lines[0][:200] if lines else "No description"


def get_skill_by_name(name: str, skills: list[Skill] | None = None) -> Skill | None:
    """Look up a skill by name from the provided or discovered skill list."""
    if skills is None:
        skills = discover_skills()
    for skill in skills:
        if skill.name == name:
            return skill
    return None
