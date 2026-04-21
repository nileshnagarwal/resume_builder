"""Fit Gatekeeper Agent — assesses match between JD requirements and master resume."""

import json

from src.llm import call_llm_json
from src.models import FitResult, JDRequirement, MatchedRequirement


SYSTEM_PROMPT = """\
You are a fit assessment specialist. Given a list of job requirements and a \
master resume, determine how well the candidate matches.

For each requirement, assess the match strength using these STRICT definitions:
- "perfect": Strongly met AND supported by a STAR bullet (Situation, Task, \
  Action, Result) with concrete metrics or outcomes.
- "full": Clearly met through narrative evidence; may lack hard metrics.
- "partial": Adjacent experience only, or evidence covers a subset of \
  the requirement.
- "weak": Very loose connection, circumstantial, or keyword-only mention.

Return JSON:
{
  "matched": [
    {
      "requirement": "requirement name",
      "reasoning": "step-by-step chain: what the requirement asks for → what bullet documents → direct logical connection between the two",
      "matched_bullets": ["exact bullet text from master resume"],
      "match_strength": "perfect" | "full" | "partial" | "weak"
    }
  ],
  "unmatched": ["requirement names with no meaningful match"],
  "recommendation": "Brief honest assessment of fit"
}

--- VALIDATION PROTOCOLS (apply all four for every requirement) ---

1. DIRECT vs ADJACENT EVIDENCE
For each matched bullet, apply this test:
"Does this bullet describe the candidate DOING the thing the requirement \
asks for, or something ADJACENT to it?"

Adjacent evidence is at most "partial". Examples of adjacent that must NOT \
receive "full" or "perfect":
- Requirement: "clinical trial management" → Bullet: "completed a pharmacology \
  course" (education about trials ≠ managing one)
- Requirement: "fluent in Mandarin" → Bullet: "worked with Mandarin-speaking \
  suppliers" (proximity to speakers ≠ fluency)
- Requirement: "financial modelling" → Bullet: "reviewed monthly P&L statements" \
  (reading reports ≠ building models)

2. SEMANTIC PRECISION
Do not conflate terms that share surface vocabulary but have different meanings:
- "Designed a patient intake system" ≠ "clinical patient care experience"
- "Managed a team in one office" ≠ "managed a geographically dispersed team"
- "Interested in pursuing" a credential ≠ "holds" that credential
- "Seeking" a role type ≠ "experienced in" that role type
State the semantic distinction explicitly in your reasoning when relevant.

3. COMPOUND REQUIREMENT DECOMPOSITION
When a requirement contains multiple sub-requirements (connected by "and", \
"as well as", or a list), decompose them and evaluate each separately. The \
overall match_strength is capped at the WEAKEST component. State each \
component verdict in the reasoning:
  "Component 1 (X): full — evidenced by [bullet]
   Component 2 (Y): unmatched — no master resume evidence.
   Overall: partial"

4. SECTION AWARENESS
The master resume may contain sections explicitly marked as non-credential \
(e.g. "PERSONAL CONTEXT", "Not part of formal credentials", "Interests", \
"Hobbies"). Content from these sections may provide supplementary context \
but must NOT be the primary or sole evidence for any match. If your only \
evidence for a requirement comes from a non-credential section, the match \
strength is "weak" at most. Prefer professional experience bullets.
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
