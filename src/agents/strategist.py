"""Strategist Agent — builds the priority map linking JD requirements to resume evidence."""

import json

from src.llm import call_llm_json
from src.models import (
    FitResult,
    JDRequirement,
    Priority,
    PriorityMap,
    PriorityMapEntry,
)


SYSTEM_PROMPT = """\
You are a resume strategist. The Fit Gatekeeper has already identified \
candidate evidence for each job requirement. Your job is to STRATEGIZE: \
rank, filter, and select the BEST bullets to use on the final resume.

You will receive:
- The JD requirements with their priority levels.
- Pre-matched evidence from the Fit Gatekeeper (bullets + match strength).
- The full master resume (for edge cases where additional evidence exists).
- The raw Job Description text.

For each requirement:
1. Review the pre-matched bullets and their match strength.
2. Provide a rationale analyzing which bullets are most strategically \
   effective for this specific requirement and why.
3. Select and rank the final bullets to use — put the most compelling first.
4. You MAY pull additional bullets from the master resume if the Gatekeeper \
   missed something compelling, but ONLY if clearly justified in the rationale.
5. COMBINATION DIRECTIVE — required in two cases:
   (a) Two or more selected bullets are weak independently but create a \
       strong story together.
   (b) Selected bullets come from different functional domains, roles, or \
       time periods and the Builder would need framing guidance to present \
       them as a coherent narrative — even if each bullet is strong on its own.
   If the Builder would need to make a judgment call about how to frame or \
   reconcile the selected bullets, you MUST provide a directive.

6. INTERVIEW-DEFENSIBILITY QUICK CHECK: Before finalising the selected \
   bullets for a requirement, ask: "If a recruiter asked the candidate to \
   elaborate on this in an interview, would each selected bullet hold up?"
   Specifically — discard any bullet that is:
   - A personal statement or job-search preference (e.g. "Open to X roles")
   - From a non-credential section of the master resume
   These are not defensible as professional credentials.

EVIDENCE-TYPE MATCHING: Read the raw JD text carefully to detect what the \
employer values most. Match the TYPE of evidence to the JD's value signal:
- If the JD emphasizes measurable outcomes (revenue, growth %, cost savings), \
  prioritize metric-heavy STAR bullets.
- If the JD emphasizes qualitative traits (trust, credibility, relationships, \
  culture, partnership), prioritize narrative evidence of those qualities — \
  even when they lack hard numbers. A bullet like "Converted first-time \
  enquiries into long-term repeat clients through transparent communication" \
  may be MORE relevant than "$830K in revenue" for a trust-focused role.
- If the JD emphasizes systems thinking or process design, prioritize \
  descriptions of systems built.

Return JSON:
{
  "entries": [
    {
      "requirement": "requirement name",
      "priority": "high" | "medium" | "low",
      "rationale": "step-by-step reasoning for why these bullets were selected and ranked this way",
      "master_resume_bullets": ["exact text from master resume"],
      "combination_directive": "Required when bullets span functional domains or are weak individually. Leave empty string if not needed."
    }
  ]
}

Rules:
- Use EXACT text from the master resume. Do not paraphrase or embellish.
- For unmatched requirements, still include the entry but with empty bullets \
  and a rationale explaining the gap.
"""



def _format_gatekeeper_evidence(fit_result: FitResult) -> str:
    """Format the Gatekeeper's matched evidence for the Strategist prompt."""
    lines = []
    for m in fit_result.matched:
        lines.append(f"### {m.requirement} [{m.match_strength}]")
        lines.append(f"Reasoning: {m.reasoning}")
        if m.matched_bullets:
            for b in m.matched_bullets:
                lines.append(f"  - {b}")
        else:
            lines.append("  (no bullets matched)")
        lines.append("")

    if fit_result.unmatched:
        lines.append("### Unmatched Requirements")
        for u in fit_result.unmatched:
            lines.append(f"  - {u}")

    return "\n".join(lines)


def build_priority_map(
    requirements: list[JDRequirement],
    fit_result: FitResult,
    master_resume_text: str,
    jd_text: str = "",
) -> PriorityMap:
    """Build a strategic priority map linking JD requirements to resume evidence."""
    req_text = "\n".join(
        f"- [{r.priority.value.upper()}] {r.name}: {r.description}"
        for r in requirements
    )
    evidence_text = _format_gatekeeper_evidence(fit_result)
    user_prompt = (
        f"## JD Requirements\n{req_text}\n\n"
        f"## Gatekeeper Evidence (pre-matched)\n{evidence_text}\n\n"
        f"## Master Resume (fallback reference)\n{master_resume_text}"
    )
    if jd_text:
        user_prompt += f"\n\n## Raw Job Description\n{jd_text}"

    raw_json = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    data = json.loads(raw_json)

    entries = []
    for e in data.get("entries", []):
        priority_str = e.get("priority", "medium").lower()
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.MEDIUM
        entries.append(
            PriorityMapEntry(
                requirement=e.get("requirement", ""),
                priority=priority,
                rationale=e.get("rationale", ""),
                master_resume_bullets=e.get("master_resume_bullets", []),
                combination_directive=e.get("combination_directive", ""),
            )
        )

    return PriorityMap(
        entries=entries,
    )

