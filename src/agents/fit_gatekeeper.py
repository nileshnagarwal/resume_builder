"""Fit Gatekeeper Agent — assesses match between JD requirements and master resume."""

import json

from src.llm import call_llm_json
from src.models import FitResult, JDRequirement, MatchedRequirement


SYSTEM_PROMPT = """\
You are a fit assessment specialist. Given a list of job requirements and a \
master resume, determine how well the candidate matches.

For each requirement, assess the match strength against the master resume using these STRICT definitions:
- "perfect": The requirement is strongly met AND supported by a clear STAR bullet (Situation, Task, Action, Result) with metrics or concrete outcomes.
- "full": The requirement is clearly met through narrative evidence, but may lack hard metrics or a strict STAR structure.
- "partial": Candidate has adjacent experience, or the evidence only covers a subset of the requirement.
- "weak": Very loose connection, circumstantial evidence, or mentioned only as a keyword without context.

Only credit matches genuinely supported by evidence — do not infer or assume.

Return JSON with this structure:
{
  "matched": [
    {
      "requirement": "requirement name",
      "reasoning": "Logical deduction on whether the master resume bullets cover the requirement and to what extent",
      "matched_bullets": ["exact bullet text from resume that proves this"],
      "match_strength": "perfect" | "full" | "partial" | "weak"
    }
  ],
  "unmatched": ["requirement names with no meaningful match"],
  "recommendation": "Brief honest assessment of fit"
}

Rules:
- Be honest. If a requirement mentions a specific tool the candidate has \
  never used, list it as unmatched even if they have adjacent experience.
"""


def assess_fit(
    requirements: list[JDRequirement],
    master_resume_text: str,
) -> FitResult:
    """Assess how well the master resume matches the JD requirements.

    Returns a FitResult with go/no-go decision and detailed matching.
    """
    req_text = "\n".join(
        f"- [{r.priority.value.upper()}] {r.name}: {r.description}"
        for r in requirements
    )
    user_prompt = (
        f"## JD Requirements\n{req_text}\n\n"
        f"## Master Resume\n{master_resume_text}"
    )

    raw_json = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    data = json.loads(raw_json)

    matched = [
        MatchedRequirement(
            requirement=m.get("requirement", ""),
            reasoning=m.get("reasoning", ""),
            matched_bullets=m.get("matched_bullets", []),
            match_strength=m.get("match_strength", "weak"),
        )
        for m in data.get("matched", [])
    ]

    unmatched = data.get("unmatched", [])

    # Calculate coverage natively
    total_reqs = len(requirements)
    coverage_pct = 0.0
    if total_reqs > 0:
        score = sum(
            1.0 if m.match_strength in ("perfect", "full") else 
            (0.5 if m.match_strength == "partial" else 0.0) 
            for m in matched
        )
        coverage_pct = (score / total_reqs) * 100.0

    return FitResult(
        matched=matched,
        unmatched=unmatched,
        recommendation=data.get("recommendation", ""),
        go=coverage_pct >= 50.0,
        coverage_pct=coverage_pct,
    )
