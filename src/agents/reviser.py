"""Reviser Agent — revises the resume draft based on critique feedback."""

import json

from src.llm import call_llm
from src.models import (
    CritiqueVerdict,
    DiffEntry,
    DraftResume,
)


SYSTEM_PROMPT = """\
You are the Resume Reviser. You receive a resume draft and critique feedback. \
Your job is to:

1. Review each critique flag and recommended change.
2. State your position on each — AGREE or DISAGREE with a reason.
3. Apply agreed changes to produce an updated resume.
4. Produce a structured DIFF LOG showing what changed and why.

FABRICATION PROHIBITION — applies to ALL critique flags from ALL agents:
Before applying any recommended change, ask: "Would satisfying this critique \
require me to add, modify, or infer content that is not present in the \
master resume?"

If YES — you MUST DISAGREE. Log it as:
  "Critique: [what was asked]. Decision: DISAGREE.
   Reason: Satisfying this would require fabricating [specific claim].
   The master resume has no evidence for it."

This applies regardless of which agent raised the flag (ATS scanner, tone cop, \
Chief Critique, hallucination checker, or any other). A critique-driven \
instruction NEVER outranks the master resume as the source of truth.

Other rules:
- You may DISAGREE with a critique point for any strong reason. \
  State the disagreement clearly.
- Use ONLY content from the master resume. Do not fabricate.
- Follow the Tone & Language Guide strictly.
- Output the COMPLETE revised resume in Markdown, not just the changes.
- Version the output (V2, V3, etc.)

Format your response as:

## DIFF LOG
[For each change, state: Location | Removed | Added | Reason]
[For disagreements, state: Critique Point | Decision: DISAGREE | Reason]

## REVISED RESUME
[Complete resume in Markdown]
"""



def revise_resume(
    current_draft: DraftResume,
    critique: CritiqueVerdict,
    master_resume_text: str,
) -> tuple[DraftResume, list[DiffEntry]]:
    """Revise the resume based on critique feedback.

    Returns the updated draft and a list of diff entries.
    """
    changes_text = "\n".join(
        f"- @ {c.location}: Remove '{c.removed}' → Add '{c.added}' "
        f"(Reason: {c.reason})"
        for c in critique.changes_recommended
    )
    flags_text = "\n".join(
        f"- [{f.severity.value}] ({f.agent_name}) @ {f.location}: "
        f"{f.issue} → {f.suggestion}"
        for f in critique.flags
    )

    user_prompt = (
        f"## Current Resume (V{current_draft.version})\n{current_draft.full_text}\n\n"
        f"## Critique Summary\n{critique.summary}\n\n"
        f"## Recommended Changes\n{changes_text}\n\n"
        f"## All Flags\n{flags_text}\n\n"
        f"## Master Resume (for fact-checking)\n{master_resume_text}"
    )

    response = call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    # Parse the response to separate diff log and revised resume
    new_version = current_draft.version + 1
    diff_entries = _extract_diff_entries(response)
    resume_text = _extract_resume_text(response)

    return (
        DraftResume(version=new_version, full_text=resume_text),
        diff_entries,
    )


def _extract_resume_text(response: str) -> str:
    """Extract the revised resume from the LLM response."""
    marker = "## REVISED RESUME"
    if marker in response:
        return response.split(marker, 1)[1].strip()
    # Fallback: if no marker found, assume the whole response is the resume
    # after any diff log section
    if "## DIFF LOG" in response:
        parts = response.split("## DIFF LOG", 1)
        if len(parts) > 1:
            # Everything after the diff log section
            remainder = parts[1]
            # Find where the resume starts (next ## heading or just text)
            lines = remainder.split("\n")
            resume_lines = []
            past_diff = False
            for line in lines:
                if past_diff:
                    resume_lines.append(line)
                elif line.strip() == "" and resume_lines:
                    past_diff = True
                elif line.startswith("## ") and "DIFF" not in line.upper():
                    past_diff = True
                    resume_lines.append(line)
            if resume_lines:
                return "\n".join(resume_lines).strip()
    return response.strip()


def _extract_diff_entries(response: str) -> list[DiffEntry]:
    """Extract diff entries from the LLM response.

    Best-effort parsing — the diff log format is semi-structured.
    """
    entries: list[DiffEntry] = []
    if "## DIFF LOG" not in response:
        return entries

    diff_section = response.split("## DIFF LOG", 1)[1]
    # Stop at the next ## heading
    if "## REVISED RESUME" in diff_section:
        diff_section = diff_section.split("## REVISED RESUME", 1)[0]
    elif "## " in diff_section[3:]:
        # Find the next heading
        next_heading_idx = diff_section.index("## ", 3)
        diff_section = diff_section[:next_heading_idx]

    for line in diff_section.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Try to parse "Location | Removed | Added | Reason" format
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p and p != "-"]
            if len(parts) >= 4:
                entries.append(
                    DiffEntry(
                        location=parts[0],
                        removed=parts[1],
                        added=parts[2],
                        reason=parts[3],
                    )
                )
            elif len(parts) >= 2:
                entries.append(
                    DiffEntry(
                        location=parts[0],
                        removed="",
                        added="",
                        reason=" | ".join(parts[1:]),
                    )
                )

    return entries
