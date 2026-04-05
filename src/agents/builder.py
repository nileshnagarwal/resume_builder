"""Builder Agent — drafts a tailored resume from the priority map."""

from src.config import BUILDER_PROMPT_PATH
from src.llm import call_llm
from src.models import DraftResume, PriorityMap


def _load_builder_instructions() -> str:
    """Load the builder instruction prompt from file."""
    return BUILDER_PROMPT_PATH.read_text(encoding="utf-8")


SYSTEM_PROMPT_TEMPLATE = """\
{builder_instructions}

---

## ADDITIONAL AUTOMATED PIPELINE CONTEXT

You are operating inside an automated pipeline. You will NOT ask the user \
any questions. Instead, use only the Priority Map and Master Resume provided \
below.

Rules for this automated run:
1. Use ONLY content from the master resume. Do not fabricate or assume.
2. Follow the priority map to decide which bullets to include and where.
3. If the Priority Map provides an optimized role title for a past job, \
   you MUST use the optimized title instead of the original title from \
   the Master Resume.
4. Format the resume in clean Markdown.
5. Summary: {summary_min}-{summary_max} bullet points.
6. Most recent role: {recent_min}-{recent_max} bullet points.
7. Past roles: {past_min}-{past_max} bullet points each.
8. Use present tense for current role, past tense for previous roles.
9. Follow the Tone & Language Guide: no hero language, plain English, \
   strong action verbs.
10. Output ONLY the resume in Markdown — no commentary, no explanations.
11. ANTI-HALLUCINATION (ALL SECTIONS): Every claim in every section — \
    Summary, Core Competencies, Experience, and any other — must be \
    traceable to specific content in the master resume. Do NOT invent \
    capabilities, activities, or experiences not documented in the master \
    resume. This includes the Summary section: do not claim "remote work \
    experience" unless the master resume explicitly describes remote work.
12. CORE COMPETENCIES: Each competency line must be a compressed summary \
    of verifiable activities from the Priority Map — not invented \
    capability claims. Do NOT add claims about tools, skills, or \
    activities not documented in the master resume.
13. Frame all qualifications positively. Do not use passive language like \
    "willing to" — use confident language like "available for" or \
    "comfortable with."
14. Match the resume's narrative tone to the JD's emphasis. If the JD \
    emphasizes trust, relationships, and credibility, lean into evidence \
    of client retention, repeat business, and transparent communication — \
    even over hard metrics.
15. ANTI-DRIFT: When rephrasing master resume content, preserve the \
    original meaning and specificity. Do not upgrade plain terms into \
    fancier corporate language. For example, do not change "business \
    reviews" to "formal presentations", or "transparent communication" \
    to "transparent stakeholder management." If the master resume says \
    it plainly, keep it plain.
"""



def draft_resume(
    priority_map: PriorityMap,
    master_resume_text: str,
    version: int = 1,
    critique_feedback: str = "",
) -> DraftResume:
    """Draft a tailored resume using the priority map and master resume.

    If critique_feedback is provided (V2+), the builder incorporates it.
    """
    from src.config import (
        MOST_RECENT_JOB_BULLET_RANGE,
        PAST_JOB_BULLET_RANGE,
        SUMMARY_BULLET_RANGE,
    )

    builder_instructions = _load_builder_instructions()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        builder_instructions=builder_instructions,
        summary_min=SUMMARY_BULLET_RANGE[0],
        summary_max=SUMMARY_BULLET_RANGE[1],
        recent_min=MOST_RECENT_JOB_BULLET_RANGE[0],
        recent_max=MOST_RECENT_JOB_BULLET_RANGE[1],
        past_min=PAST_JOB_BULLET_RANGE[0],
        past_max=PAST_JOB_BULLET_RANGE[1],
    )

    priority_map_text = "\n".join(
        f"### {e.requirement} [{e.priority.value}]\n"
        f"Bullets: {chr(10).join('- ' + b for b in e.master_resume_bullets)}\n"
        f"Rationale: {e.rationale}"
        + (f"\nCombination Directive: {e.combination_directive}" if e.combination_directive else "")
        for e in priority_map.entries
    )

    # Format optimized role titles
    title_text = ""
    if priority_map.optimized_role_titles:
        title_lines = []
        for t in priority_map.optimized_role_titles:
            if t.original_title != t.optimized_title:
                title_lines.append(f"- {t.original_title} → {t.optimized_title}")
            else:
                title_lines.append(f"- {t.original_title} (no change)")
        title_text = "\n".join(title_lines)

    user_prompt = (
        f"## Priority Map\n{priority_map_text}\n\n"
    )
    if title_text:
        user_prompt += f"## Optimized Role Titles\n{title_text}\n\n"
    user_prompt += f"## Master Resume\n{master_resume_text}"

    if critique_feedback:
        user_prompt += (
            f"\n\n## Critique Feedback (Version {version - 1})\n"
            f"Address the following feedback in this revision:\n{critique_feedback}"
        )

    resume_text = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
    )

    return DraftResume(
        version=version,
        full_text=resume_text,
    )
