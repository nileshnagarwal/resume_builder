"""JD Extractor Agent — extracts requirements from a job description."""

import json

from src.llm import call_llm_json
from src.models import JDRequirement, Priority


SYSTEM_PROMPT = """\
You are a job description analyst. Extract ALL requirements from the given \
job description — both explicit and implicit.

For each requirement, provide:
- source_statement: The exact statement(s) from the JD. Quote if explicit, provide context if implicit.
- reasoning: Logical step-by-step reasoning for extracting this requirement.
- name: a short label (e.g. "B2B Sales Experience")
- description: what exactly is required
- priority: "high" (must-have / listed under Required), "medium" (preferred / \
  nice-to-have), or "low" (implied but not stated)
- keywords: ATS-relevant keywords a recruiter would search for

Return a JSON array of objects. Example:
[
  {
    "source_statement": "Proven track record in driving business growth.",
    "reasoning": "The JD explicitly asks for driving business growth, which means business development or sales experience.",
    "name": "B2B Sales Experience",
    "description": "Experience in business development, partnerships, or client acquisition",
    "priority": "high",
    "keywords": ["B2B", "sales", "business development", "client acquisition"]
  }
]

Be thorough. Include requirements implied by the role context even if not \
explicitly listed (e.g. a remote role implies "comfortable working remotely").
"""


def extract_requirements(jd_text: str) -> list[JDRequirement]:
    """Extract structured requirements from raw JD text.

    Returns a list of JDRequirement objects sorted by priority (high first).
    """
    raw_json = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Extract all requirements from this job description:\n\n{jd_text}",
    )
    items = json.loads(raw_json)
    requirements = []
    for item in items:
        # Normalize priority to our enum
        priority_str = item.get("priority", "medium").lower()
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.MEDIUM

        requirements.append(
            JDRequirement(
                source_statement=item.get("source_statement", ""),
                reasoning=item.get("reasoning", ""),
                name=item.get("name", "Unknown"),
                description=item.get("description", ""),
                priority=priority,
                keywords=item.get("keywords", []),
            )
        )

    # Sort: high first, then medium, then low
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    requirements.sort(key=lambda r: priority_order[r.priority])
    return requirements
