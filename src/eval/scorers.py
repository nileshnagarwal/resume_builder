"""Deterministic scorers for the eval harness.

Every scorer returns a list of AgentScore objects and tags findings with
ErrorCodes from the formal taxonomy.
"""

import re
from typing import Optional

from src.models import PipelineState
from src.eval.scoring import AgentScore, AgentTrace
from src.eval.error_taxonomy import ErrorCode
from src.validators import validate_bullet_counts
from src.config import BANNED_HERO_WORDS
from src.vector_db import query_similar


# ---------------------------------------------------------------------------
# Fit Gatekeeper Scorers
# ---------------------------------------------------------------------------

def score_fit_verdict(
    pair_id: str,
    expected_go: bool | None,
    expected_cov: tuple[float, float] | None,
    state: PipelineState,
) -> list[AgentScore]:
    scores = []

    if state.fit_result is None:
        return scores

    fit = state.fit_result

    # 1. Verdict match
    if expected_go is not None:
        correct = fit.go == expected_go
        score = 5.0 if correct else 1.0
        expected_str = "GO" if expected_go else "NO-GO"
        actual_str = "GO" if fit.go else "NO-GO"

        error_codes = []
        error_details = []
        if not correct:
            code = ErrorCode.GK_FALSE_GO if fit.go else ErrorCode.GK_FALSE_NOGO
            error_codes.append(code.value)
            error_details.append({
                "code": code.value,
                "location": "fit_result.go",
                "evidence": f"Expected {expected_str}, got {actual_str}",
                "severity": "blocker",
            })

        scores.append(AgentScore(
            agent_name="Fit Gatekeeper",
            dimension="Verdict Accuracy",
            score=score,
            max_score=5.0,
            method="deterministic",
            notes=f"Expected {expected_str}, got {actual_str}",
            error_codes=error_codes,
            error_details=error_details,
        ))

    # 2. Coverage range
    if expected_cov is not None:
        low, high = expected_cov
        in_range = low <= fit.coverage_pct <= high
        score = 5.0 if in_range else 1.0

        error_codes = []
        error_details = []
        if not in_range:
            code = ErrorCode.GK_GRADE_INFLATION if fit.coverage_pct > high else ErrorCode.GK_FALSE_NOGO
            error_codes.append(code.value)
            error_details.append({
                "code": code.value,
                "location": "fit_result.coverage_pct",
                "evidence": f"Expected {low}%-{high}%, got {fit.coverage_pct}%",
                "severity": "blocker",
            })

        scores.append(AgentScore(
            agent_name="Fit Gatekeeper",
            dimension="Coverage Range",
            score=score,
            max_score=5.0,
            method="deterministic",
            notes=f"Expected {low}%-{high}%, got {fit.coverage_pct}%",
            error_codes=error_codes,
            error_details=error_details,
        ))

    return scores


# ---------------------------------------------------------------------------
# Builder Scorers
# ---------------------------------------------------------------------------

def score_bullet_counts(state: PipelineState) -> list[AgentScore]:
    if not state.current_draft:
        return []

    violations = validate_bullet_counts(state.current_draft.full_text)

    score = 5.0 if not violations else 1.0
    notes = "Valid" if not violations else f"{len(violations)} violations: " + ", ".join(v.message for v in violations)

    error_codes = [ErrorCode.BL_STRUCTURAL_VIOLATION.value] if violations else []
    error_details = [
        {
            "code": ErrorCode.BL_STRUCTURAL_VIOLATION.value,
            "location": v.section,
            "evidence": v.message,
            "severity": "blocker",
        }
        for v in violations
    ]

    return [AgentScore(
        agent_name="Builder",
        dimension="Bullet Counts",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


def score_banned_words(state: PipelineState) -> list[AgentScore]:
    if not state.current_draft:
        return []

    text = state.current_draft.full_text.lower()
    found = [w for w in BANNED_HERO_WORDS if w in text]

    score = 5.0 if not found else 1.0
    notes = "No banned words" if not found else f"Found: {', '.join(found)}"

    error_codes = [ErrorCode.BL_OVERCLAIMING_LANGUAGE.value] if found else []
    error_details = [
        {
            "code": ErrorCode.BL_OVERCLAIMING_LANGUAGE.value,
            "location": "full_text",
            "evidence": f"Banned word: '{w}'",
            "severity": "blocker",
        }
        for w in found
    ]

    return [AgentScore(
        agent_name="Builder",
        dimension="Tone Compliance (Deterministic)",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


def score_hallucination_surface(state: PipelineState) -> list[AgentScore]:
    if not state.current_draft:
        return []

    # Extract bullets from final resume
    bullets = []
    lines = state.current_draft.full_text.split('\n')
    for line in lines:
        if re.match(r"^\s*[\*\-]\s+", line):
            bullets.append(line.strip().lstrip("*- "))

    if not bullets:
        return []

    master_text = state.master_resume_text.lower()
    suspicious = []

    for bullet in bullets:
        # Simple trigram match
        words = [w for w in re.split(r'\W+', bullet.lower()) if len(w) > 3]
        if len(words) < 3:
            continue

        found_any = False
        for i in range(len(words)-2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            if trigram in master_text:
                found_any = True
                break

        if not found_any:
            suspicious.append(bullet[:40] + "...")

    score = 5.0 if not suspicious else max(1.0, 5.0 - len(suspicious))
    notes = "Pass" if not suspicious else f"{len(suspicious)} suspicious bullets without trigram match in master."

    error_codes = [ErrorCode.BL_UNSOURCED_CLAIM.value] if suspicious else []
    error_details = [
        {
            "code": ErrorCode.BL_UNSOURCED_CLAIM.value,
            "location": "resume bullet",
            "evidence": b,
            "severity": "improvement",
        }
        for b in suspicious
    ]

    return [AgentScore(
        agent_name="Builder",
        dimension="No Hallucinations (Surface Match)",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


def score_semantic_similarity(state: PipelineState) -> list[AgentScore]:
    """Score bullets based on semantic overlap with the master resume."""
    if not state.current_draft:
        return []

    # Extract bullets from final resume
    bullets = []
    lines = state.current_draft.full_text.split('\n')
    for line in lines:
        if re.match(r"^\s*[\*\-]\s+", line):
            bullets.append(line.strip().lstrip("*- "))

    if not bullets:
        return []

    suspicious = []

    for bullet in bullets:
        # ChromaDB query returns L2 distance by default.
        # Generally, a distance < 1.0 means it's semantically close. > 1.2 is divergent.
        results = query_similar(bullet, n_results=1)
        if not results:
            suspicious.append(bullet[:40] + "...")
            continue

        dist = results[0].get("distance", 0.0)
        if dist > 1.2:  # Threshold for "unsupported hallucination"
            suspicious.append(f"{bullet[:30]}... (Dist: {dist:.2f})")

    score = 5.0 if not suspicious else max(1.0, 5.0 - len(suspicious))
    notes = "Pass" if not suspicious else f"{len(suspicious)} bullets lacked semantic backing."

    error_codes = [ErrorCode.BL_UNSOURCED_CLAIM.value] if suspicious else []
    error_details = [
        {
            "code": ErrorCode.BL_UNSOURCED_CLAIM.value,
            "location": "resume bullet",
            "evidence": b,
            "severity": "improvement",
        }
        for b in suspicious
    ]

    return [AgentScore(
        agent_name="Builder",
        dimension="Semantic Fact-Checking",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


# ---------------------------------------------------------------------------
# NEW: Metric Fidelity — catches BL-001 (Metric Inflation) deterministically
# ---------------------------------------------------------------------------

# Pattern matches common resume metrics: 35%, $830K, 40+, 12M, etc.
_NUMBER_PATTERN = re.compile(
    r"""
    (?:~|\$|≈)?              # optional prefix: ~, $, ≈
    \d[\d,]*                 # digits (possibly with commas)
    (?:\.\d+)?               # optional decimal
    (?:\s*[%KMB+])?          # optional suffix: %, K, M, B, +
    """,
    re.VERBOSE,
)


def _extract_numbers(text: str) -> set[str]:
    """Extract normalised numeric tokens from text.

    Normalises by stripping whitespace, commas, and leading ~ / $ / ≈
    so that '$830K' and '830K' match.
    """
    raw = _NUMBER_PATTERN.findall(text)
    normalised = set()
    for token in raw:
        n = token.strip().lstrip("~$≈ ").replace(",", "").strip()
        if n:
            normalised.add(n)
    return normalised


def score_metric_fidelity(state: PipelineState) -> list[AgentScore]:
    """Flag numbers in the resume that don't appear in the master resume."""
    if not state.current_draft or not state.master_resume_text:
        return []

    resume_numbers = _extract_numbers(state.current_draft.full_text)
    master_numbers = _extract_numbers(state.master_resume_text)

    if not resume_numbers:
        return []

    unmatched = resume_numbers - master_numbers
    # Filter out trivially small numbers (1-digit) that are likely formatting
    unmatched = {n for n in unmatched if len(n.rstrip("%KMB+")) > 1}

    score = 5.0 if not unmatched else max(1.0, 5.0 - len(unmatched))
    notes = "All metrics traceable" if not unmatched else f"{len(unmatched)} unmatched: {', '.join(sorted(unmatched))}"

    error_codes = [ErrorCode.BL_METRIC_INFLATION.value] if unmatched else []
    error_details = [
        {
            "code": ErrorCode.BL_METRIC_INFLATION.value,
            "location": "resume metric",
            "evidence": f"Number '{n}' not found in master resume",
            "severity": "blocker",
        }
        for n in sorted(unmatched)
    ]

    return [AgentScore(
        agent_name="Builder",
        dimension="Metric Fidelity",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


# ---------------------------------------------------------------------------
# NEW: Priority Alignment — checks structural placement of high-priority reqs
# ---------------------------------------------------------------------------

def score_priority_alignment(state: PipelineState) -> list[AgentScore]:
    """Check that HIGH-priority requirements appear in prominent resume sections.

    'Prominent' = Summary section or most recent role (first ~40% of resume text).
    """
    if not state.current_draft or not state.requirements or not state.priority_map:
        return []

    high_reqs = [r for r in state.requirements if r.priority.value == "high"]
    if not high_reqs:
        return []

    # Use first 40% of resume as "prominent zone"
    full_text = state.current_draft.full_text.lower()
    cutoff = int(len(full_text) * 0.4)
    prominent_zone = full_text[:cutoff]

    # Get keywords from high-priority requirements
    buried = []
    for req in high_reqs:
        # Check if any of the requirement's keywords appear in the prominent zone
        keywords = [kw.lower() for kw in req.keywords] + [req.name.lower()]
        in_prominent = any(kw in prominent_zone for kw in keywords if len(kw) > 3)
        in_full = any(kw in full_text for kw in keywords if len(kw) > 3)

        if in_full and not in_prominent:
            buried.append(req.name)

    score = 5.0 if not buried else max(1.0, 5.0 - len(buried))
    notes = "All high-priority requirements in prominent sections" if not buried else (
        f"{len(buried)} high-priority reqs buried in lower sections: {', '.join(buried)}"
    )

    error_codes = [ErrorCode.ST_PRIORITY_INVERSION.value] if buried else []
    error_details = [
        {
            "code": ErrorCode.ST_PRIORITY_INVERSION.value,
            "location": "resume structure",
            "evidence": f"High-priority requirement '{name}' not found in top 40% of resume",
            "severity": "improvement",
        }
        for name in buried
    ]

    return [AgentScore(
        agent_name="Strategist",
        dimension="Priority Alignment",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
        error_codes=error_codes,
        error_details=error_details,
    )]


# ---------------------------------------------------------------------------
# NEW: Loop Efficiency — measures how quickly the pipeline converges
# ---------------------------------------------------------------------------

def score_loop_efficiency(
    traces: list[AgentTrace],
    loops_to_ready: Optional[int],
) -> list[AgentScore]:
    """Score based on how many revision loops were needed.

    5.0 = submission_ready after first critique (V2)
    3.0 = needed one extra loop (V3)
    1.0 = hit max loops or never reached submission_ready
    """
    if loops_to_ready is None:
        score = 0.0
        notes = "Never reached submission_ready"
    elif loops_to_ready <= 1:
        score = 5.0
        notes = f"Submission-ready at V2 ({loops_to_ready} revision loop)"
    elif loops_to_ready == 2:
        score = 3.0
        notes = f"Submission-ready at V3 ({loops_to_ready} revision loops)"
    else:
        score = 1.0
        notes = f"Needed {loops_to_ready} revision loops"

    return [AgentScore(
        agent_name="Pipeline",
        dimension="Loop Efficiency",
        score=score,
        max_score=5.0,
        method="deterministic",
        notes=notes,
    )]
