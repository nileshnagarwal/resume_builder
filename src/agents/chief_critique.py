"""Chief Critique Agent — synthesizes flags from the critique swarm into a verdict."""

import json

from src.llm import call_llm_json
from src.models import (
    CritiqueFlag,
    CritiqueVerdict,
    DiffEntry,
    DraftResume,
    Severity,
    SubmissionVerdict,
)


SYSTEM_PROMPT = """\
You are the Chief Critique agent. You receive flags from 4 specialized \
critique agents (hallucination checker, tone cop, formatting inspector, \
ATS scanner) and must synthesize them into a final verdict.

Your responsibilities:
1. Filter out false positives — if a flag is clearly wrong, discard it.
2. Resolve conflicts — if the ATS scanner wants a keyword but the tone cop \
   bans it, follow this hierarchy: Hallucination > Tone > Formatting > ATS.
3. Check job title alignment — does the title match the JD's seniority?
4. Produce a SUBMISSION VERDICT:
   - "submission_ready" — no blockers remain
   - "needs_fixes" — has fixable issues, worth one more revision
   - "not_ready" — fundamental problems

SEVERITY CALIBRATION — the hierarchy also governs severity assignment:
- Only HALLUCINATION flags may be assigned "blocker" severity. A fabricated \
  claim is the only legitimate blocker.
- TONE and FORMATTING flags are always "improvement" unless they introduce a \
  factual distortion (in which case they become hallucination flags).
- ATS keyword flags are ALWAYS "improvement" or "optional" — NEVER "blocker". \
  A missing keyword must never trigger fabrication downstream. If you receive \
  an ATS flag marked "blocker", downgrade it to "improvement" before passing it through.

FEASIBILITY GATE: Before passing any flag to the Reviser, ask:
"Can this flag be addressed using only content already in the master resume?"
If NO — if satisfying it would require inventing content — discard the flag \
entirely and note it in your summary as a confirmed gap.

Return JSON:
{
  "verdict": "submission_ready" | "needs_fixes" | "not_ready",
  "flags": [
    {
      "agent_name": "which agent raised it",
      "severity": "blocker" | "improvement" | "optional",
      "location": "where",
      "issue": "what",
      "suggestion": "how to fix"
    }
  ],
  "changes_recommended": [
    {
      "location": "where to change",
      "removed": "what to remove",
      "added": "what to add",
      "reason": "why"
    }
  ],
  "summary": "Overall assessment in 2-3 sentences"
}

Be rigorous but fair. Do not recommend changes for cosmetic preferences.
"""



def synthesize_critique(
    flags: list[CritiqueFlag],
    draft: DraftResume,
) -> CritiqueVerdict:
    """Synthesize critique swarm flags into a final verdict."""
    flags_text = "\n".join(
        f"- [{f.severity.value}] ({f.agent_name}) @ {f.location}: "
        f"{f.issue} → {f.suggestion}"
        for f in flags
    )

    user_prompt = (
        f"## Critique Flags ({len(flags)} total)\n{flags_text}\n\n"
        f"## Resume Draft (V{draft.version})\n{draft.full_text}"
    )

    raw = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    data = json.loads(raw)

    verdict_str = data.get("verdict", "needs_fixes")
    try:
        verdict = SubmissionVerdict(verdict_str)
    except ValueError:
        verdict = SubmissionVerdict.NEEDS_FIXES

    parsed_flags = []
    for f in data.get("flags", []):
        severity_str = f.get("severity", "improvement")
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.IMPROVEMENT
        parsed_flags.append(
            CritiqueFlag(
                agent_name=f.get("agent_name", "chief_critique"),
                severity=severity,
                location=f.get("location", ""),
                issue=f.get("issue", ""),
                suggestion=f.get("suggestion", ""),
            )
        )

    changes = [
        DiffEntry(
            location=c.get("location", ""),
            removed=c.get("removed", ""),
            added=c.get("added", ""),
            reason=c.get("reason", ""),
        )
        for c in data.get("changes_recommended", [])
    ]

    return CritiqueVerdict(
        verdict=verdict,
        flags=parsed_flags,
        changes_recommended=changes,
        summary=data.get("summary", ""),
    )
