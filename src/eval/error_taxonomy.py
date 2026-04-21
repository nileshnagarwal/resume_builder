"""Formal error taxonomy for eval findings.

Every finding — whether from a deterministic scorer or an LLM judge — is tagged
with one or more ErrorCodes.  This shared vocabulary replaces ad-hoc notes and
makes scores comparable across runs, agents, and evaluators.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """Canonical error types, grouped by the agent that causes them."""

    # --- JD Extractor Errors ---
    EX_MISSING_IMPLICIT = "EX-001"        # Failed to extract implicit JD requirements
    EX_OVER_EXTRACTION = "EX-002"         # Extracted requirements not present in JD
    EX_POOR_PRIORITIZATION = "EX-003"     # Wrong priority assigned to requirement

    # --- Gatekeeper Errors ---
    GK_GRADE_INFLATION = "GK-001"         # Assigns full/perfect to a partial/weak match
    GK_GAP_CREDIT = "GK-002"              # Credits a confirmed gap as a match
    GK_FALSE_GO = "GK-003"                # GO on an obviously unqualified profile
    GK_FALSE_NOGO = "GK-004"              # NO-GO on a clearly qualified profile
    GK_GRADE_DEFLATION = "GK-005"         # Assigns partial/weak to a match that is clearly full/perfect

    # --- Strategist Errors ---
    ST_PRIORITY_INVERSION = "ST-001"      # High-priority req served by weak evidence
    ST_EVIDENCE_TYPE_MISMATCH = "ST-002"  # Metric bullets for a trust/narrative JD
    ST_WEAK_PULL = "ST-003"               # Pulls bullets Gatekeeper marked as weak
    ST_DIRECTIVE_ABSENT = "ST-004"        # No combination_directive when bullets need synthesis

    # --- Builder Errors ---
    BL_METRIC_INFLATION = "BL-001"        # "~$830K" becomes "nearly $1M"
    BL_KEYWORD_HALLUCINATION = "BL-002"   # Injects JD keywords not in master resume
    BL_SCOPE_INFLATION = "BL-003"         # Overstates responsibility scope
    BL_CHRONOLOGICAL_DRIFT = "BL-004"     # Misattributes work to wrong time period
    BL_GAP_PAPERING = "BL-005"            # Covers confirmed gap with adjacent experience
    BL_UNSOURCED_CLAIM = "BL-006"         # Claim has no master resume backing
    BL_OVERCLAIMING_LANGUAGE = "BL-007"   # Hero words, corporate-speak
    BL_STRUCTURAL_VIOLATION = "BL-008"    # Bullet counts, tense, format
    BL_FILLER = "BL-009"                  # Non-achievement statements
    BL_DIRECTIVE_VIOLATION = "BL-010"     # Ignores strategist combination_directive

    # --- Critique / Reviser Errors ---
    CR_FALSE_PASS = "CR-001"              # Swarm misses a real issue
    CR_FALSE_FLAG = "CR-002"              # Swarm flags legitimate content
    CR_REGRESSION = "CR-003"              # Revision fixes one issue, introduces another
    CR_HIERARCHY_VIOLATION = "CR-004"     # Chief ignores priority hierarchy
    CR_PREMATURE_READY = "CR-005"         # submission_ready with active blockers

    # --- Title Optimizer Errors ---
    TO_SENIORITY_INFLATION = "TO-001"     # Title overstates actual seniority held
    TO_SENIORITY_DEFLATION = "TO-002"     # Title downplays actual seniority unnecessarily
    TO_FUNCTION_DRIFT = "TO-003"          # Title changes the function (e.g. ops → sales)
    TO_RESPONSIBILITY_MISMATCH = "TO-004" # Title mismatches with the listed duties


# Convenience groupings for evaluators that sweep per-agent.
EXTRACTOR_ERRORS = {ErrorCode.EX_MISSING_IMPLICIT, ErrorCode.EX_OVER_EXTRACTION, ErrorCode.EX_POOR_PRIORITIZATION}
GATEKEEPER_ERRORS = {ErrorCode.GK_GRADE_INFLATION, ErrorCode.GK_GAP_CREDIT, ErrorCode.GK_FALSE_GO, ErrorCode.GK_FALSE_NOGO, ErrorCode.GK_GRADE_DEFLATION}
STRATEGIST_ERRORS = {ErrorCode.ST_PRIORITY_INVERSION, ErrorCode.ST_EVIDENCE_TYPE_MISMATCH, ErrorCode.ST_WEAK_PULL, ErrorCode.ST_DIRECTIVE_ABSENT}
BUILDER_ERRORS = {e for e in ErrorCode if e.value.startswith("BL-")}
CRITIQUE_ERRORS = {e for e in ErrorCode if e.value.startswith("CR-")}
TITLE_OPTIMIZER_ERRORS = {e for e in ErrorCode if e.value.startswith("TO-")}
