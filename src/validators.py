"""Deterministic validators for resume drafts.

These run as code — not LLM calls — for 100% reliability and zero API cost.
"""

import re
from dataclasses import dataclass

from src.config import (
    MOST_RECENT_JOB_BULLET_RANGE,
    PAST_JOB_BULLET_RANGE,
    SUMMARY_BULLET_RANGE,
)


@dataclass
class BulletCountViolation:
    """A single bullet-count violation."""
    section: str
    actual: int
    expected_min: int
    expected_max: int

    @property
    def message(self) -> str:
        return (
            f"{self.section}: {self.actual} bullets "
            f"(expected {self.expected_min}-{self.expected_max})"
        )


def _count_bullets_in_block(lines: list[str]) -> int:
    """Count markdown bullet lines (lines starting with * or -)."""
    return sum(
        1 for line in lines
        if re.match(r"^\s*[\*\-]\s+", line)
    )


def _split_resume_sections(resume_text: str) -> dict[str, list[str]]:
    """Split a markdown resume into named sections by bold headers.

    Recognises patterns like:
        **PROFESSIONAL EXPERIENCE**
        **NIMBUS LOGISTICS | Mumbai, India**
        **Founder & Sales and Operations Manager | Dec 2016 – Dec 2025**

    Returns a dict of {header_text: [lines under that header]}.
    """
    lines = resume_text.split("\n")
    sections: dict[str, list[str]] = {}
    current_key: str | None = None

    for line in lines:
        # Match lines that are **BOLD TEXT** (section headers or job headers)
        header_match = re.match(r"^\*\*(.+?)\*\*\s*$", line.strip())
        if header_match:
            current_key = header_match.group(1).strip()
            sections[current_key] = []
        elif current_key is not None:
            sections[current_key].append(line)

    return sections


def validate_bullet_counts(resume_text: str) -> list[BulletCountViolation]:
    """Validate bullet counts in a resume draft.

    Returns a list of violations. Empty list = all checks pass.

    Detection logic:
    - The SUMMARY is the section before the first job heading (contains
      the job title and bullet points before PROFESSIONAL EXPERIENCE).
    - The MOST RECENT role is the first company-level section under
      PROFESSIONAL EXPERIENCE.
    - All subsequent company-level sections are PAST roles.
    """
    sections = _split_resume_sections(resume_text)
    violations: list[BulletCountViolation] = []

    # --- Identify sections ---
    # Find the summary: content between the name/title and PROFESSIONAL EXPERIENCE
    # We look for bullets that appear before any job company header
    all_lines = resume_text.split("\n")

    # Find summary bullets: bullets between the start and "PROFESSIONAL EXPERIENCE"
    summary_bullets = 0
    in_summary = False
    for line in all_lines:
        stripped = line.strip()
        # Start counting after the job title header
        if re.match(r"^\*\*[A-Z].*(?:MANAGER|DIRECTOR|LEAD|ENGINEER|ANALYST)", stripped):
            in_summary = True
            continue
        if "PROFESSIONAL EXPERIENCE" in stripped.upper():
            break
        if "CORE COMPETENCIES" in stripped.upper():
            break
        if in_summary and re.match(r"^\s*[\*\-]\s+", stripped):
            summary_bullets += 1

    if summary_bullets > 0:
        s_min, s_max = SUMMARY_BULLET_RANGE
        if summary_bullets < s_min or summary_bullets > s_max:
            violations.append(BulletCountViolation(
                section="Summary",
                actual=summary_bullets,
                expected_min=s_min,
                expected_max=s_max,
            ))

    # --- Find job sections under PROFESSIONAL EXPERIENCE ---
    # Company headers: "NIMBUS LOGISTICS | Mumbai, India"  (first word is ALL CAPS)
    # Job title sub-headers: "Founder & Sales Manager | Dec 2016" (Title Case)
    # We group all job-title bullet blocks under their parent company.
    job_sections: list[tuple[str, int]] = []  # (company_name, total_bullets)
    in_experience = False
    current_company: str | None = None
    current_bullet_count: int = 0

    for key, lines in sections.items():
        key_upper = key.upper()
        if "PROFESSIONAL EXPERIENCE" in key_upper:
            in_experience = True
            continue
        if not in_experience:
            continue
        # Stop if we hit non-job sections
        if any(s in key_upper for s in [
            "TECHNICAL SKILLS", "EDUCATION", "CERTIFICATIONS",
            "PROJECTS", "VOLUNTEER",
        ]):
            break

        # Distinguish company header from job title sub-header:
        # Company header first word is all-uppercase (e.g. "NIMBUS")
        first_word = key.strip().split()[0].rstrip("|, ")
        is_company_header = "|" in key and first_word == first_word.upper() and first_word.isalpha()

        if is_company_header:
            # Save the previous company before starting a new one
            if current_company is not None:
                job_sections.append((current_company, current_bullet_count))
            current_company = key
            current_bullet_count = _count_bullets_in_block(lines)
        elif current_company is not None:
            # Job title or sub-header under the current company — accumulate bullets
            current_bullet_count += _count_bullets_in_block(lines)

    if current_company is not None:
        job_sections.append((current_company, current_bullet_count))

    # --- Validate job bullet counts ---
    for i, (company_name, bullet_count) in enumerate(job_sections):
        if bullet_count == 0:
            continue

        if i == 0:
            # Most recent role
            r_min, r_max = MOST_RECENT_JOB_BULLET_RANGE
            label = f"Most Recent Role ({company_name.split('|')[0].strip()})"
        else:
            # Past role
            r_min, r_max = PAST_JOB_BULLET_RANGE
            label = f"Past Role ({company_name.split('|')[0].strip()})"

        if bullet_count < r_min or bullet_count > r_max:
            violations.append(BulletCountViolation(
                section=label,
                actual=bullet_count,
                expected_min=r_min,
                expected_max=r_max,
            ))

    return violations

