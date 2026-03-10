"""Execute skill-based plan reviews and multi-agent refinement."""

import logging
from dataclasses import dataclass

from app.config import Settings
from app.rag.llm import get_completion
from app.rag.prompts import build_skill_review_messages
from app.rag.retriever import Retriever
from app.skills.loader import Skill, discover_skills

logger = logging.getLogger(__name__)


@dataclass
class SkillReview:
    """Result of a skill-based plan review."""

    skill_name: str
    review: str
    issues: list[str]
    approvals: list[str]


def run_skill_review(plan: str, skill: Skill, retriever: Retriever,
                     settings: Settings | None = None) -> SkillReview:
    """Run a single skill review against a plan."""
    settings = settings or Settings.get()

    # Search for context relevant to the plan
    results = retriever.search(plan[:500], top_k=5)
    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    messages = build_skill_review_messages(
        plan=plan,
        skill_description=skill.content,
        documents=documents,
        metadatas=metadatas,
    )

    try:
        response = get_completion(messages, settings)
    except RuntimeError as e:
        logger.error("Skill review failed for %s: %s", skill.name, e)
        return SkillReview(
            skill_name=skill.name,
            review=f"Review failed: {e}",
            issues=[],
            approvals=[],
        )

    issues = _extract_items(response, markers=["warning", "issue", "concern", "risk"])
    approvals = _extract_items(response, markers=["good", "approved", "correct", "solid"])

    return SkillReview(
        skill_name=skill.name,
        review=response,
        issues=issues,
        approvals=approvals,
    )


def run_multi_skill_review(plan: str, skill_names: list[str],
                           retriever: Retriever,
                           settings: Settings | None = None,
                           custom_skills_dir: str | None = None) -> list[SkillReview]:
    """Run reviews from multiple skills against a plan."""
    settings = settings or Settings.get()
    skills = discover_skills(custom_dir=custom_skills_dir)

    reviews: list[SkillReview] = []
    for name in skill_names:
        skill = next((s for s in skills if s.name == name), None)
        if skill is None:
            logger.warning("Skill not found: %s", name)
            reviews.append(SkillReview(
                skill_name=name,
                review=f"Skill '{name}' not found.",
                issues=[],
                approvals=[],
            ))
            continue

        logger.info("Running review: %s", name)
        review = run_skill_review(plan, skill, retriever, settings)
        reviews.append(review)

    return reviews


def refine_plan_with_reviews(plan: str, reviews: list[SkillReview],
                             settings: Settings | None = None) -> str:
    """Refine a plan by incorporating feedback from skill reviews."""
    settings = settings or Settings.get()

    review_summary = ""
    for r in reviews:
        review_summary += f"\n## {r.skill_name} Review:\n{r.review}\n"

    messages = [
        {"role": "system",
         "content": ("You are a planning assistant. Refine the plan based on "
                     "specialist feedback. Incorporate valid suggestions and "
                     "explain any changes made.")},
        {"role": "user",
         "content": (f"Original Plan:\n{plan}\n\n"
                     f"Specialist Reviews:\n{review_summary}\n\n"
                     f"Produce a refined plan incorporating the feedback.")},
    ]

    try:
        return get_completion(messages, settings)
    except RuntimeError as e:
        logger.error("Plan refinement failed: %s", e)
        raise RuntimeError(
            f"Plan refinement failed (LLM error): {e}. Original plan is unchanged."
        ) from e


def _extract_items(text: str, markers: list[str]) -> list[str]:
    """Extract lines from text that contain any of the given marker words."""
    items: list[str] = []
    for line in text.split("\n"):
        line_lower = line.strip().lower()
        for marker in markers:
            if marker in line_lower:
                items.append(line.strip())
                break
    return items


def format_reviews(reviews: list[SkillReview]) -> str:
    """Format a list of skill reviews into a readable markdown string."""
    parts: list[str] = []
    for r in reviews:
        parts.append(f"### {r.skill_name}")
        parts.append(r.review)
        if r.issues:
            parts.append("\n**Issues found:**")
            for issue in r.issues:
                parts.append(f"- {issue}")
        if r.approvals:
            parts.append("\n**Approved:**")
            for approval in r.approvals:
                parts.append(f"- {approval}")
        parts.append("---")
    return "\n".join(parts)
