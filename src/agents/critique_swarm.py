"""Critique Swarm — 3 parallel mini-agents that check the resume draft."""

import asyncio
import difflib
import json
import re

from src.config import BANNED_HERO_WORDS
from src.llm import call_llm, call_llm_json
from src.models import (
    CritiqueFlag,
    DiffEntry,
    DraftResume,
    JDRequirement,
    Severity,
)


# ---------------------------------------------------------------------------
# Hallucination Checker — Two-Tier Architecture
#
# Tier 1 (deterministic): fast string similarity filter.
#   Lines that closely match any substring of the master resume are auto-CLEAN.
#   No LLM cost, no lazy-exit incentive.
#
# Tier 2 (LLM — Logical Bridge): only non-verbatim lines reach this agent.
#   It must articulate an explicit evidence→claim transformation chain and
#   apply an "interview-defensibility" test before marking anything CLEAN.
#   Vague topical similarity is NOT sufficient — the logical bridge must hold.
# ---------------------------------------------------------------------------

_VERBATIM_THRESHOLD = 0.82  # SequenceMatcher ratio; tune if false-positive rate rises
_MARKDOWN_STRIP_RE = re.compile(r"[\*\_\#\[\]\(\)`]+")


def _normalise(text: str) -> str:
    """Strip markdown, collapse whitespace, lowercase for comparison."""
    text = _MARKDOWN_STRIP_RE.sub(" ", text)
    return " ".join(text.lower().split())


def _split_into_checkable_lines(full_text: str) -> list[str]:
    """Return non-empty, non-header-only lines worth auditing."""
    lines = []
    for raw in full_text.splitlines():
        stripped = raw.strip()
        # Skip blank lines and pure section headers (no content after ##)
        if not stripped or re.fullmatch(r"#+\s*", stripped):
            continue
        lines.append(stripped)
    return lines


def _is_verbatim_match(line: str, master_text: str, threshold: float = _VERBATIM_THRESHOLD) -> bool:
    """Return True when *line* is a near-verbatim paraphrase of some passage
    in *master_text*.

    Uses a sliding window of the same token-length as *line* over *master_text*
    so that localised matches are not diluted by the full-document comparison.
    """
    norm_line = _normalise(line)
    norm_master = _normalise(master_text)

    if not norm_line:
        return True  # empty / whitespace-only → nothing to hallucinate

    # Quick whole-document check first (cheap)
    if norm_line in norm_master:
        return True

    # Sliding window: compare against same-length windows of master text
    words_line = norm_line.split()
    words_master = norm_master.split()
    window = len(words_line)

    best = 0.0
    for start in range(max(1, len(words_master) - window + 1)):
        chunk = " ".join(words_master[start : start + window + 5])  # +5 slack
        ratio = difflib.SequenceMatcher(None, norm_line, chunk).ratio()
        if ratio > best:
            best = ratio
        if best >= threshold:
            return True

    return best >= threshold


# --- Tier-2: Logical Bridge Prompt ---

LOGICAL_BRIDGE_PROMPT = """\
You are a Hallucination Auditor performing a DEEP EVIDENCE CHECK on specific \
claims from a resume draft.

For each claim provided, you MUST complete the following four steps IN ORDER. \
Do not skip any step.

STEP 1 — EVIDENCE
Quote the most relevant passage from the master resume verbatim.
If no relevant passage exists, write: NONE

STEP 2 — TRANSFORMATION BRIDGE
Explain, step by step, how the evidence passage logically and honestly becomes \
the draft claim — without distortion, omission, or escalation of scope.
- If the claim is a close paraphrase of the evidence, state: \
"VERBATIM PARAPHRASE — no transformation needed."
- If the claim reframes the candidate's role, identity, competency level, \
or relationship to clients/employers in a way not derivable from the evidence, \
state that the bridge FAILS and explain why.
- The bridge FAILS if: the evidence describes doing X but the claim says being Y \
(role identity drift), the evidence hedges but the claim is definitive, or the \
evidence covers a different domain than the claim.

STEP 3 — INTERVIEW DEFENSIBILITY TEST
Ask: "Could the candidate say this specific phrasing in a recruiter interview \
and defend it against 'What exactly do you mean by that?' using ONLY what the \
master resume documents?"
Answer YES or NO, with one sentence of justification.

STEP 4 — VERDICT
Mark the claim as one of:
  <CLEAN>        — bridge holds AND interview-defensible
  <HALLUCINATION> — bridge fails OR not interview-defensible

After completing ALL claims, output a JSON summary:
[
  {
    "severity": "blocker",
    "location": "exact section and phrase from draft",
    "issue": "what is wrong and why the bridge failed",
    "suggestion": "how to rewrite using only master resume content"
  }
]

Only include <HALLUCINATION> items in the JSON. Return [] if all claims are clean.

IMPORTANT: Topical similarity is NOT sufficient for <CLEAN>. The transformation \
bridge must be explicit and defensible. If you cannot complete Step 2 honestly, \
the claim is a hallucination.
"""



async def _check_hallucinations(
    draft: DraftResume,
    master_resume_text: str,
    *,
    previous_flags: list[CritiqueFlag] | None = None,
    diff_log: list[DiffEntry] | None = None,
) -> tuple[str, list[CritiqueFlag]]:
    """Two-tier hallucination check.

    Loop 0: full resume — tier-1 verbatim filter, then tier-2 bridge LLM for
    any non-verbatim lines.

    Loop 1+: only diff lines + previously-flagged locations are re-checked,
    skipping unchanged clean content entirely.
    """
    is_first_loop = not diff_log and not previous_flags

    # --- Determine which lines to audit ---
    if is_first_loop:
        candidate_lines = _split_into_checkable_lines(draft.full_text)
    else:
        # Build the candidate set from diff additions + prior flag locations
        candidate_lines: list[str] = []

        if diff_log:
            for entry in diff_log:
                if entry.added and entry.added.strip():
                    candidate_lines.extend(
                        _split_into_checkable_lines(entry.added)
                    )

        if previous_flags:
            # Re-check any line that was previously flagged — confirm the fix
            all_draft_lines = _split_into_checkable_lines(draft.full_text)
            flagged_locations = {
                f.location.lower() for f in previous_flags
                if f.agent_name == "hallucination_checker"
            }
            for line in all_draft_lines:
                for loc in flagged_locations:
                    if any(word in _normalise(line) for word in loc.split() if len(word) > 4):
                        candidate_lines.append(line)
                        break

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for ln in candidate_lines:
            if ln not in seen:
                seen.add(ln)
                unique.append(ln)
        candidate_lines = unique

    if not candidate_lines:
        return "(no lines to check — all content verbatim or unchanged)", []

    # --- Tier 1: deterministic verbatim filter ---
    non_verbatim = [
        line for line in candidate_lines
        if not _is_verbatim_match(line, master_resume_text)
    ]

    tier1_note = (
        f"Tier-1 filter: {len(candidate_lines)} lines checked, "
        f"{len(candidate_lines) - len(non_verbatim)} auto-CLEAN (verbatim), "
        f"{len(non_verbatim)} forwarded to Logical Bridge LLM."
    )

    if not non_verbatim:
        return tier1_note, []

    # --- Tier 2: Logical Bridge LLM ---
    claims_block = "\n".join(
        f"{i+1}. {line}" for i, line in enumerate(non_verbatim)
    )
    user_prompt = (
        f"## Claims to Audit ({len(non_verbatim)} non-verbatim lines)\n"
        f"{claims_block}\n\n"
        f"## Master Resume\n{master_resume_text}"
    )
    raw = call_llm(
        system_prompt=LOGICAL_BRIDGE_PROMPT,
        user_prompt=user_prompt,
    )
    json_text = _extract_json_from_response(raw)
    scratchpad = f"{tier1_note}\n\n{raw}"
    return scratchpad, _parse_flags(json_text, "hallucination_checker")




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
    previous_flags: list[CritiqueFlag] | None = None,
    diff_log: list[DiffEntry] | None = None,
) -> list[CritiqueFlag] | tuple[list[CritiqueFlag], list]:
    """Run all 3 critique agents in parallel and return combined flags.

    When ``emit_traces=True``, returns a (flags, sub_traces) tuple where
    sub_traces is a list of AgentTrace objects — one per sub-agent.

    ``previous_flags`` and ``diff_log`` enable incremental HC checking on
    loop 1+: only diff lines and previously-flagged locations are re-audited.
    """
    return asyncio.run(
        _run_swarm_async(
            draft, master_resume_text, requirements,
            emit_traces=emit_traces,
            loop_iteration=loop_iteration,
            previous_flags=previous_flags,
            diff_log=diff_log,
        )
    )


async def _run_swarm_async(
    draft: DraftResume,
    master_resume_text: str,
    requirements: list[JDRequirement],
    *,
    emit_traces: bool = False,
    loop_iteration: int = 0,
    previous_flags: list[CritiqueFlag] | None = None,
    diff_log: list[DiffEntry] | None = None,
) -> list[CritiqueFlag] | tuple[list[CritiqueFlag], list]:
    """Run all 3 critique checks concurrently."""
    import time as _time

    sub_agents = [
        (
            "hallucination_checker",
            _check_hallucinations(
                draft, master_resume_text,
                previous_flags=previous_flags,
                diff_log=diff_log,
            ),
        ),
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
