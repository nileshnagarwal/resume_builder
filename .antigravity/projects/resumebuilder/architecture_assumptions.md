# Architecture & Formatting Assumptions

This document acts as a ledger for all hardcoded assumptions made across the pipeline (prompts, validators, parsing logic). If you change how you want the resume to look or function, you must cross-reference this list to see what code or prompts will break.

## 1. Resume Structural Assumptions
Currently hardcoded in [src/validators.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/validators.py) and relied upon by the `Builder` and [Critique](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/models.py#113-123) agents.

*   **Section Headers:** Major sections use bold, all-caps strings (e.g. `**PROFESSIONAL EXPERIENCE**`). The word "PROFESSIONAL EXPERIENCE" specifically acts as the anchor dividing the Summary/Core Competencies from the roles.
*   **Company Headers vs Job Titles:** 
    *   Company headers must contain a pipe (`|`) and the first word MUST be entirely uppercase (e.g., `**NIMBUS LOGISTICS | Mumbai, India**`).
    *   Job title sub-headers contain a pipe (`|`) but the first word must NOT be all uppercase (e.g., `**Founder & Sales Manager | Dec 2016**`).
    *   *Why this matters:* The programmatic bullet counter uses this exact distinction to group bullets under companies to enforce the max-bullet rules.
*   **Markdown Bullets:** Bullets must start with `* ` or `- `. Our programmatic validator uses the regex `^\s*[\*\-]\s+` to count them.

## 2. Pipeline Economics Assumptions
Currently documented in [root_cause_analysis.md](file:///Users/nileshagarwal/.gemini/antigravity/brain/3197aa58-e2bb-4856-a7c3-2e6f907038f9/root_cause_analysis.md).

*   **API Context Caching Limit:** Gemini API requires a strict minimum of 32,768 tokens to enable cache creation. We assume that in V1, the Master Profile + JD will NOT exceed this limit (~19K tokens currently), meaning we operate without caching unless we switch to an alternative provider like Anthropic Claude 3.5 (minimum 1,024 tokens).
*   **The Master Profile grows linearly:** The Updater Agent will indefinitely append missing context to ChromaDB, eventually pushing the Master Profile over the 32K token threshold for caching.

## 3. Scope Boundaries
*   **Resume length:** We do not enforce a hard page limit programmatically, though we target standard 1-2 page formatting via strict bullet count limits (max 6 for recent, max 3 for past).
*   **Tone overrides:** We assume the Tone Cop's rules (no "hero" words, active voice) trump any ATS Keyword Scanner rules for the exact same semantic keyword. The Chief Critique resolves these conflicts.
