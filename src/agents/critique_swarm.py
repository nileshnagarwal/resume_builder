"""Critique Swarm — 3 parallel mini-agents that check the resume draft."""

import asyncio
import json

from src.config import BANNED_HERO_WORDS
from src.llm import call_llm, call_llm_json
from src.models import (
    CritiqueFlag,
    DraftResume,
    JDRequirement,
    Severity,
)


# --- Hallucination Checker ---

HALLUCINATION_PROMPT = """\
You are a hallucination detection agent. Perform a LINE-BY-LINE audit of the \
resume draft against the master resume.

Do not accept implied context. If the draft states that a task was performed under specific conditions (e.g., 'remote environments', 'distributed teams', 'agile squads', 'startup incubators'), that exact environmental context MUST exist explicitly in the master resume. You cannot infer that because they have a certain skill, they operated in that environment.

For EVERY line of the resume draft, output exactly one of:

  <CLEAN> <Draft Phrase>
  Reasoning: <Why it is supported>
  Evidence: <Master resume quote>

  <HALLUCINATION> <Draft Phrase>
  Claimed: <what the draft says>
  Master resume says: <what is actually documented>
  Severity: blocker

Do NOT group lines. Do NOT skip lines. Do NOT write section summaries instead \
of line-by-line output. Process top to bottom.

Lines requiring extra scrutiny:
- Any "Experienced in X" or "Expert in Y" in the Professional Summary \
  (treat as factual claims, not framing — verify X and Y exist in master resume)
- Any environmental or circumstantial framing (e.g. 'remote', 'fast-paced', 'executive-level')
- Any tool, platform, or methodology named in Core Competencies or Skills \
  (each must be traceable to documented use in master resume)
- All numbers, percentages, and dollar figures in Experience bullets \
  (flag if they differ even slightly from master resume)
- Any phrase that sounds like a JD keyword but has no master resume referent \
  (e.g. "webinar delivery", "strategic alliances", "SaaS expertise" must all \
  have master resume evidence)

After the line-by-line output, append a JSON summary:
[
  {
    "severity": "blocker",
    "location": "section and line description",
    "issue": "what was fabricated or assumed",
    "suggestion": "what to do about it"
  }
]

Only include hallucinations in the JSON — not clean lines. Return [] if none.
"""



async def _check_hallucinations(
    draft: DraftResume,
    master_resume_text: str,
) -> tuple[str, list[CritiqueFlag]]:
    user_prompt = (
        f"## Resume Draft\n{draft.full_text}\n\n"
        f"## Master Resume\n{master_resume_text}"
    )
    # Response is line-by-line audit + JSON array; extract just the JSON
    raw = call_llm(
        system_prompt=HALLUCINATION_PROMPT,
        user_prompt=user_prompt,
    )
    json_text = _extract_json_from_response(raw)
    return raw, _parse_flags(json_text, "hallucination_checker")




# --- Tone & Language Cop ---

TONE_PROMPT = """\
You are a tone and language reviewer. Check the resume draft for:
1. Hero language: words like {banned_words}
2. Tense violations: current roles (e.g. 'Present') must use present tense, past roles must use past tense. Use the provided current date to determine if a hardcoded end-date (like 'Dec 2025') is in the past. Do not flag past dates as future errors.
3. Abstract or multi-clause sentences that violate plain English
4. Buzzwords or phrases that cannot be said naturally in an interview
5. Numbers that appear estimated or inflated

Return JSON array:
[
  {{
    "severity": "improvement" or "blocker",
    "location": "section and bullet",
    "issue": "what the problem is",
    "suggestion": "how to fix it"
  }}
]

Return empty array [] if everything is clean.
""".format(banned_words=", ".join(BANNED_HERO_WORDS))


async def _check_tone(draft: DraftResume) -> tuple[str, list[CritiqueFlag]]:
    import datetime
    current_date = datetime.datetime.now().strftime("%B %Y")
    user_prompt = (
        f"## Context\nToday's date is: {current_date}\n\n"
        f"## Resume Draft\n{draft.full_text}"
    )
    raw = call_llm(
        system_prompt=TONE_PROMPT,
        user_prompt=user_prompt,
    )
    json_text = _extract_json_from_response(raw)
    return raw, _parse_flags(json_text, "tone_cop")


# --- ATS Keyword Scanner ---

ATS_PROMPT = """\
You are an ATS keyword scanner. Given a resume draft, the required keywords, \
and the candidate's MASTER RESUME, check which critical keywords are absent.

FEASIBILITY CHECK — mandatory before flagging anything:
For EVERY required keyword listed, you must first verify if the candidate actually possesses the skill by checking the MASTER RESUME.

Show your work for each keyword:
<KEYWORD> Keyword name
Evidence: Quote the master resume proving they have the skill, or write "NONE" if they don't have it
Status: <MISSING_KEYWORD> | <GENUINE_GAP> | <PRESENT_IN_DRAFT>

Rules for Status:
- <PRESENT_IN_DRAFT>: The keyword is already in the draft. (Do nothing)
- <GENUINE_GAP>: The Evidence is "NONE". The candidate has never done this. Do NOT flag it for insertion. This is an honest gap and inserting it would be a hallucination.
- <MISSING_KEYWORD>: The Evidence exists, BUT the keyword is missing from the draft. The core builder just forgot to include it.

After your scratchpad, return a JSON array containing ONLY the <MISSING_KEYWORD> items:
[
  {
    "severity": "improvement",
    "location": "suggested insertion point",
    "issue": "missing keyword: X",
    "suggestion": "natural way to include using existing master resume content",
    "master_resume_evidence": "brief quote from master resume confirming candidate has this"
  }
]

Return empty array [] if all critical keywords are covered or all absences \
are confirmed gaps.
"""



async def _check_ats_keywords(
    draft: DraftResume,
    requirements: list[JDRequirement],
    master_resume_text: str,
) -> tuple[str, list[CritiqueFlag]]:
    # Only check medium/high priority keywords to avoid bloating with low-priority items
    target_reqs = [r for r in requirements if r.priority.value in ["high", "medium"]]
    
    req_text = json.dumps([r.model_dump() for r in target_reqs], indent=2)
    user_prompt = (
        f"## Priority Requirements (High/Medium Only)\n{req_text}\n\n"
        f"## Master Resume\n{master_resume_text}\n\n"
        f"## Current Resume Draft\n{draft.full_text}"
    )
    
    raw = call_llm(
        system_prompt=ATS_PROMPT,
        user_prompt=user_prompt,
    )
    json_text = _extract_json_from_response(raw)
    return raw, _parse_flags(json_text, "ats_scanner")



# --- Shared Parser ---

def _extract_json_from_response(response: str) -> str:
    """Extract the JSON array from a mixed text+JSON LLM response.

    Scratchpad lines now use <CLEAN> / <HALLUCINATION> XML-style tags, so '['
    only ever appears as part of the JSON array payload.  We can therefore
    scan forward from the first '[' and bracket-balance to the matching ']'.
    """
    start = response.find("[")
    if start == -1:
        return "[]"

    depth = 0
    in_string = False
    escape = False

    for i, ch in enumerate(response[start:], start=start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return response[start: i + 1].strip()

    # Malformed / no closing bracket — return empty list so downstream doesn't crash
    return "[]"


def _parse_flags(raw_json: str, agent_name: str) -> list[CritiqueFlag]:
    """Parse raw JSON into CritiqueFlag objects."""
    items = json.loads(raw_json)
    if not isinstance(items, list):
        items = []
    flags = []
    for item in items:
        severity_str = item.get("severity", "improvement").lower()
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.IMPROVEMENT
        flags.append(
            CritiqueFlag(
                agent_name=agent_name,
                severity=severity,
                location=item.get("location", "unknown"),
                issue=item.get("issue", ""),
                suggestion=item.get("suggestion", ""),
            )
        )
    return flags


# --- Public API ---

def run_critique_swarm(
    draft: DraftResume,
    master_resume_text: str,
    requirements: list[JDRequirement],
    *,
    emit_traces: bool = False,
    loop_iteration: int = 0,
) -> list[CritiqueFlag] | tuple[list[CritiqueFlag], list]:
    """Run all 3 critique agents in parallel and return combined flags.

    When ``emit_traces=True``, returns a (flags, sub_traces) tuple where
    sub_traces is a list of AgentTrace objects — one per sub-agent.
    """
    return asyncio.run(
        _run_swarm_async(draft, master_resume_text, requirements,
                         emit_traces=emit_traces,
                         loop_iteration=loop_iteration)
    )


async def _run_swarm_async(
    draft: DraftResume,
    master_resume_text: str,
    requirements: list[JDRequirement],
    *,
    emit_traces: bool = False,
    loop_iteration: int = 0,
) -> list[CritiqueFlag] | tuple[list[CritiqueFlag], list]:
    """Run all 3 critique checks concurrently."""
    import time as _time

    sub_agents = [
        ("hallucination_checker", _check_hallucinations(draft, master_resume_text)),
        ("tone_language_cop", _check_tone(draft)),
        ("ats_keyword_scanner", _check_ats_keywords(draft, requirements, master_resume_text)),
    ]


    all_flags: list[CritiqueFlag] = []
    sub_traces: list = []

    if emit_traces:
        from src.eval.scoring import AgentTrace, _safe_serialize

        # Run each sub-agent with individual timing
        for agent_name, coro in sub_agents:
            start = _time.time()
            raw_text = ""
            try:
                raw_text, flags = await coro
            except Exception as exc:
                flags = [CritiqueFlag(
                    agent_name="critique_swarm",
                    severity=Severity.IMPROVEMENT,
                    location="system",
                    issue=f"Critique sub-agent '{agent_name}' failed: {exc}",
                    suggestion="Manually review this aspect",
                )]
            elapsed = _time.time() - start

            all_flags.extend(flags)

            sub_traces.append(AgentTrace(
                agent_name=agent_name,
                loop_iteration=loop_iteration,
                state_before={
                    "current_draft": draft.full_text,
                    "draft_version": draft.version,
                    "requirements_count": len(requirements),
                },
                state_after={
                    "flags": [f.model_dump() for f in flags],
                    "flag_count": len(flags),
                    "reasoning_scratchpad": raw_text,
                },
                elapsed_seconds=elapsed,
            ))

        return all_flags, sub_traces

    # Non-tracing path: use asyncio.gather for maximum concurrency
    results = await asyncio.gather(
        *[coro for _, coro in sub_agents],
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, Exception):
            all_flags.append(
                CritiqueFlag(
                    agent_name="critique_swarm",
                    severity=Severity.IMPROVEMENT,
                    location="system",
                    issue=f"Critique sub-agent failed: {result}",
                    suggestion="Manually review this aspect",
                )
            )
        else:
            all_flags.extend(result)

    return all_flags
