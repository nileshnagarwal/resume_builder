"""Critique Swarm — 4 parallel mini-agents that check the resume draft."""

import asyncio
import json

from src.config import BANNED_HERO_WORDS
from src.llm import call_llm_json
from src.models import (
    CritiqueFlag,
    DraftResume,
    JDRequirement,
    Severity,
)


# --- Hallucination Checker ---

HALLUCINATION_PROMPT = """\
You are a hallucination detection agent. Compare the resume draft against the \
master resume. Flag ANY claim, number, metric, or responsibility in the draft \
that is NOT explicitly present in the master resume.

Return JSON array:
[
  {
    "severity": "blocker",
    "location": "section and bullet where the issue is",
    "issue": "what was fabricated or assumed",
    "suggestion": "what to do about it"
  }
]

Return an empty array [] if no hallucinations found.
Be strict — if a number differs even slightly from the master resume, flag it.
"""


async def _check_hallucinations(
    draft: DraftResume,
    master_resume_text: str,
) -> list[CritiqueFlag]:
    user_prompt = (
        f"## Resume Draft\n{draft.full_text}\n\n"
        f"## Master Resume\n{master_resume_text}"
    )
    raw = call_llm_json(
        system_prompt=HALLUCINATION_PROMPT,
        user_prompt=user_prompt,
    )
    return _parse_flags(raw, "hallucination_checker")


# --- Tone & Language Cop ---

TONE_PROMPT = """\
You are a tone and language reviewer. Check the resume draft for:
1. Hero language: words like {banned_words}
2. Tense violations: current role should be present tense, past roles past tense
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


async def _check_tone(draft: DraftResume) -> list[CritiqueFlag]:
    raw = call_llm_json(
        system_prompt=TONE_PROMPT,
        user_prompt=f"Review this resume for tone and language:\n\n{draft.full_text}",
    )
    return _parse_flags(raw, "tone_language_cop")


# --- Formatting Inspector ---

FORMATTING_PROMPT = """\
You are a formatting inspector. Check the resume draft for structural rules:
1. Professional Summary: exactly 3-4 bullet points
2. Most recent job: exactly 5-6 bullet points
3. Each past job: exactly 2-3 bullet points
4. Each section must have a clear heading
5. No duplicate content across sections

Count bullets for EVERY section and report the count explicitly.

Return JSON array:
[
  {
    "severity": "blocker" or "improvement",
    "location": "section name",
    "issue": "e.g. 'Summary has 5 bullets, expected 3-4'",
    "suggestion": "what to do"
  }
]

Return empty array [] if formatting is correct.
"""


async def _check_formatting(draft: DraftResume) -> list[CritiqueFlag]:
    raw = call_llm_json(
        system_prompt=FORMATTING_PROMPT,
        user_prompt=f"Check formatting of this resume:\n\n{draft.full_text}",
    )
    return _parse_flags(raw, "formatting_inspector")


# --- ATS Keyword Scanner ---

ATS_PROMPT = """\
You are an ATS keyword scanner. Given a resume draft and a list of job \
requirements with their keywords, check which critical keywords are present \
and which are missing.

Only flag HIGH priority keywords that are completely absent from the resume.
Do not suggest keyword stuffing — only flag natural insertion opportunities.

Return JSON array:
[
  {
    "severity": "improvement" or "blocker",
    "location": "suggested insertion point",
    "issue": "missing keyword: X",
    "suggestion": "natural way to include it"
  }
]

Return empty array [] if all critical keywords are covered.
"""


async def _check_ats_keywords(
    draft: DraftResume,
    requirements: list[JDRequirement],
) -> list[CritiqueFlag]:
    keywords_text = "\n".join(
        f"- [{r.priority.value}] {r.name}: {', '.join(r.keywords)}"
        for r in requirements
    )
    user_prompt = (
        f"## Resume Draft\n{draft.full_text}\n\n"
        f"## Required Keywords\n{keywords_text}"
    )
    raw = call_llm_json(
        system_prompt=ATS_PROMPT,
        user_prompt=user_prompt,
    )
    return _parse_flags(raw, "ats_keyword_scanner")


# --- Shared Parser ---

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
) -> list[CritiqueFlag]:
    """Run all 4 critique agents in parallel and return combined flags."""
    return asyncio.run(
        _run_swarm_async(draft, master_resume_text, requirements)
    )


async def _run_swarm_async(
    draft: DraftResume,
    master_resume_text: str,
    requirements: list[JDRequirement],
) -> list[CritiqueFlag]:
    """Run all 4 critique checks concurrently."""
    results = await asyncio.gather(
        _check_hallucinations(draft, master_resume_text),
        _check_tone(draft),
        _check_formatting(draft),
        _check_ats_keywords(draft, requirements),
        return_exceptions=True,
    )

    all_flags: list[CritiqueFlag] = []
    for result in results:
        if isinstance(result, Exception):
            # If an individual checker fails, add a warning flag
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
