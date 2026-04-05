"""Pydantic models for inter-agent data contracts."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(str, Enum):
    BLOCKER = "blocker"
    IMPROVEMENT = "improvement"
    OPTIONAL = "optional"


class SubmissionVerdict(str, Enum):
    SUBMISSION_READY = "submission_ready"
    NEEDS_FIXES = "needs_fixes"
    NOT_READY = "not_ready"


# --- JD Extraction ---

class JDRequirement(BaseModel):
    """A single requirement extracted from a job description."""
    source_statement: str = Field(
        description="The statement(s) from the JD. Quote explicitly if present, or provide context if implicit.",
    )
    reasoning: str = Field(
        description="Logical step-by-step reasoning for extracting this requirement from the statement.",
    )
    name: str = Field(description="Short name of the requirement")
    description: str = Field(description="Full description of what is required")
    priority: Priority = Field(description="How critical this requirement is")
    keywords: list[str] = Field(
        default_factory=list,
        description="ATS-relevant keywords for this requirement",
    )


# --- Fit Assessment ---

class MatchedRequirement(BaseModel):
    """A JD requirement matched against the master resume."""
    requirement: str = Field(description="Name of the JD requirement")
    reasoning: str = Field(description="Step-by-step reasoning for how well the master resume matches this requirement")
    matched_bullets: list[str] = Field(
        description="Master resume bullets that address this requirement",
    )
    match_strength: str = Field(description="full, partial, or weak")


class FitResult(BaseModel):
    """Output of the Fit Gatekeeper agent."""
    matched: list[MatchedRequirement] = Field(default_factory=list)
    unmatched: list[str] = Field(
        default_factory=list,
        description="JD requirements with no match in master resume",
    )
    recommendation: str = Field(
        default="",
        description="Brief assessment of fit quality",
    )
    go: bool = Field(description="Whether to proceed with resume generation")
    coverage_pct: float = Field(description="Percentage of JD requirements covered")


# --- Strategy ---

class PriorityMapEntry(BaseModel):
    """Maps a JD requirement to the best master resume evidence."""
    requirement: str
    priority: Priority
    rationale: str = Field(description="Why these bullets were chosen")
    master_resume_bullets: list[str] = Field(
        description="Best STAR bullets from master resume for this requirement",
    )
    combination_directive: str = Field(
        default="",
        description="Instructions to the Builder on how to combine or synthesize these bullets.",
    )


class RoleTitleRewrite(BaseModel):
    """An optimized title for a historical role on the resume."""
    original_title: str = Field(description="The exact title as it appears in the master resume")
    rationale: str = Field(description="Why this rewrite is honest and better aligned with the JD")
    optimized_title: str = Field(description="The ATS-optimized title for this specific application")


class PriorityMap(BaseModel):
    """Full strategic mapping of JD requirements to resume evidence."""
    entries: list[PriorityMapEntry] = Field(default_factory=list)
    optimized_role_titles: list[RoleTitleRewrite] = Field(
        default_factory=list,
        description="Per-role title rewrites from the Title Optimizer agent",
    )


# --- Resume Draft ---

class ResumeSection(BaseModel):
    """A section of the generated resume."""
    heading: str
    bullets: list[str] = Field(default_factory=list)
    raw_text: str = Field(
        default="",
        description="Full text if not bullet-based (e.g. contact header)",
    )


class DraftResume(BaseModel):
    """A complete resume draft."""
    version: int = Field(default=1)
    sections: list[ResumeSection] = Field(default_factory=list)
    full_text: str = Field(
        default="",
        description="The complete resume as markdown text",
    )


# --- Critique ---

class CritiqueFlag(BaseModel):
    """A single finding from a critique sub-agent."""
    agent_name: str = Field(description="Which critique agent raised this flag")
    severity: Severity
    location: str = Field(description="Where in the resume the issue is")
    issue: str = Field(description="What the problem is")
    suggestion: str = Field(
        default="",
        description="How to fix it",
    )


class DiffEntry(BaseModel):
    """A single change made during revision."""
    location: str
    removed: str
    added: str
    reason: str


class CritiqueVerdict(BaseModel):
    """Final synthesized critique from the Chief Critique."""
    verdict: SubmissionVerdict
    flags: list[CritiqueFlag] = Field(default_factory=list)
    changes_recommended: list[DiffEntry] = Field(default_factory=list)
    summary: str = Field(default="", description="Overall assessment")


# --- Pipeline State (LangGraph) ---

class PipelineState(BaseModel):
    """The state object that flows through the LangGraph pipeline."""
    # Inputs
    jd_text: str = ""
    master_resume_text: str = ""

    # Stage outputs
    requirements: list[JDRequirement] = Field(default_factory=list)
    fit_result: Optional[FitResult] = None
    priority_map: Optional[PriorityMap] = None
    current_draft: Optional[DraftResume] = None
    critique_flags: list[CritiqueFlag] = Field(default_factory=list)
    critique_verdict: Optional[CritiqueVerdict] = None
    diff_log: list[DiffEntry] = Field(default_factory=list)

    # Loop control
    loop_count: int = 0

    # Final output
    final_resume_md: str = ""
