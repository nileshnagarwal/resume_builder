# Claude Cowork — Eval Instructions

You are evaluating a single run of the ResumeBuilder AI pipeline. Your job is to audit **every agent** in the pipeline using the formal error taxonomy provided.

---

## Files in This Directory

Read them in order:

| File | Contains | Use For |
|------|----------|---------|
| `01_jd_requirements.json` | JD Extractor output | Evaluate EX-001 through EX-003 |
| `02_fit_result.json` | Gatekeeper output | Evaluate GK-001 through GK-005 |
| `03_priority_map.json` | Strategist + Title Optimizer output | Evaluate ST-001 through ST-004, TO-001 through TO-004 |
| `04_final_resume.md` | Builder output — the tailored resume | Evaluate BL-001 through BL-010 |
| `05_traces.json` | Full pipeline traces — state_before + state_after per agent, per loop iteration | Evaluate CR-001 through CR-005; use `state_before["current_draft"]` to see what draft each critique sub-agent reviewed |
| `06_deterministic_scores.json` | Automated scorer results (already run) | Cross-reference — do not re-score these dimensions |
| `07_error_taxonomy.py` | Formal error code definitions | Reference for all error codes |
| `08_eval_instructions.md` | This file | Your operating instructions |
| `09_master_resume.md` | The candidate's FULL master resume | Ground truth for every factual claim |

---

## Your Evaluation Scope

### 1. JD Extractor (file: `01_jd_requirements.json`)

Sweep for:
- **EX-001 (Missing Implicit)**: Did the extractor miss requirements that are implicit in the JD but not stated verbatim?
- **EX-002 (Over-Extraction)**: Did the extractor fabricate requirements that aren't in the JD?
- **EX-003 (Poor Prioritization)**: Are priority assignments correct? A passing mention should not be HIGH.

### 2. Fit Gatekeeper (file: `02_fit_result.json`)

Sweep for:
- **GK-001 (Grade Inflation)**: Are any `match_strength` values inflated? Does `full` really mean full coverage?
- **GK-002 (Gap Credit)**: Does any matched requirement rely on a confirmed gap from the master resume?
- **GK-003 (False GO)**: If the verdict is GO, was it justified by the evidence?
- **GK-004 (False NO-GO)**: If the verdict is NO-GO, was the candidate actually qualified?

### 3. Strategist (file: `03_priority_map.json`)

Sweep for:
- **ST-001 (Priority Inversion)**: Are the strongest master resume bullets assigned to the highest-priority requirements?
- **ST-002 (Evidence Type Mismatch)**: For a relationship/trust JD, does the strategist favour narrative bullets? For a metrics-heavy JD, does it favour quantitative bullets?
- **ST-003 (Weak Pull)**: Does the strategist use bullets the Gatekeeper marked as `weak`?
- **ST-004 (Directive Absent)**: When multiple bullets must be synthesized, is there a `combination_directive`?

### 4. Title Optimizer (file: `03_priority_map.json` → `optimized_role_titles`)

Sweep for:
- **TO-001 (Seniority Inflation)**: Does any rewritten title overstate the candidate's actual seniority?
- **TO-002 (Seniority Deflation)**: Does any rewritten title unnecessarily downplay seniority?
- **TO-003 (Function Drift)**: Does any title change the functional area (e.g., operations → sales)?
- **TO-004 (Responsibility Mismatch)**: Does any title contradict the duties listed under it?

### 5. Builder (file: `04_final_resume.md`, cross-reference with `09_master_resume.md`)

Sweep for:
- **BL-001 (Metric Inflation)**: Any number in the resume that differs from the master resume.
- **BL-002 (Keyword Hallucination)**: JD keywords injected into the resume without master resume backing.
- **BL-003 (Scope Inflation)**: Responsibilities described more broadly than the master resume documents.
- **BL-004 (Chronological Drift)**: Work attributed to the wrong role or time period.
- **BL-005 (Gap Papering)**: Confirmed gaps covered by adjacent but different experience.
- **BL-006 (Unsourced Claim)**: Any claim with no traceable master resume bullet.
- **BL-007 (Overclaiming Language)**: Hero words, corporate-speak, AI-sounding prose.
- **BL-008 (Structural Violation)**: Bullet count, tense, or format violations (cross-check with `06_deterministic_scores.json`).
- **BL-009 (Filler)**: Non-achievement statements ("team player", "results-driven").
- **BL-010 (Directive Violation)**: Builder ignores the Strategist's `combination_directive`.

### 6. Hallucination Checker (file: `05_traces.json` → `hallucination_checker` entries)

Sweep for:
- **CR-001 (False Pass)**: Did it miss a fabricated claim in the draft — especially in the Summary or Core Competencies sections?
- **CR-002 (False Flag)**: Did it flag a claim that is clearly supported by the master resume?

### 7. Tone & Language Cop (file: `05_traces.json` → `tone_cop` entries)

Sweep for:
- **CR-001 (False Pass)**: Did it miss a banned hero word or AI-sounding phrase present in the draft?
- **CR-002 (False Flag)**: Did it flag an acceptable, down-to-earth action verb as overclaiming?

### 8. ATS Keyword Scanner (file: `05_traces.json` → `ats_scanner` entries)

Sweep for:
- **CR-001 (False Pass)**: Did it miss a high-priority JD keyword that the candidate genuinely has and that the Builder omitted?
- **CR-002 (False Flag)**: Did it flag a keyword as missing when it was actually present (possibly under slightly different phrasing)? Did it flag a genuine skills gap as a missing keyword, creating hallucination pressure on the Reviser?

### 9. Chief Critique (file: `05_traces.json` → `chief_critique` entries)

> Apply GIGO Isolation: score the Chief only on how it synthesised the sub-agent flags it received, not on the quality of those flags themselves.

Sweep for:
- **CR-004 (Hierarchy Violation)**: Did the Chief violate the Hallucination > Tone > Formatting > ATS priority order when resolving conflicts?
- **CR-005 (Premature Ready)**: Was `submission_ready` issued while Blocker-severity flags were still listed in its own output?

### 10. Reviser (file: `05_traces.json` → `reviser` entries)

> Apply GIGO Isolation: score the Reviser only on how it executed the Chief's instructions, not on whether those instructions were correct.

Sweep for:
- **CR-003 (Regression)**: Did a revision fix one flag but introduce a new problem elsewhere in the draft?
- **CR-001 (False Pass via fabrication)**: Did the Reviser invent content to satisfy a flag rather than finding evidence in the master resume?

---

## Output Format

Return a single JSON array of findings. Each finding must use this schema and evaluate **each specific run (loop iteration)** of an agent:

```json
[
  {
    "agent_name": "Builder",
    "loop_iteration": 1,
    "error_code": "BL-001",
    "dimension": "Metric Fidelity",
    "score": 2,
    "max_score": 5,
    "location": "Nimbus Logistics, bullet 3",
    "evidence": "Resume says '$1M revenue' but master resume says '~$830K'",
    "severity": "blocker",
    "recommendation": "Use the exact figure from the master resume: '~$830K'"
  },
  {
    "agent_name": "Hallucination Checker",
    "loop_iteration": 1,
    "error_code": "CR-001",
    "dimension": "Hallucination Recall",
    "score": 2,
    "max_score": 5,
    "location": "Professional Summary, bullet 4",
    "evidence": "'Expert in building strategic alliances' was not flagged despite no master resume evidence of alliances",
    "severity": "blocker",
    "recommendation": "Hallucination Checker must sweep Summary and Core Competencies, not just Experience bullets"
  }
]
```

> **Important:** Critique Swarm sub-agents are scored independently. Emit a separate finding object for each of: `Hallucination Checker`, `Tone & Language Cop`, `ATS Keyword Scanner`, `Chief Critique`, and `Reviser`. Do NOT collapse them into a single `Critique / Reviser` finding.

### Rules

1. **Evaluate Per-Loop Iteration:** For agents that run multiple times (Builder, Hallucination Checker, Tone Cop, ATS Scanner, Chief Critique, Reviser), you MUST evaluate each loop separately. If the Builder runs 3 times, you must output at least 3 findings for the Builder (one for `loop_iteration: 1`, `loop_iteration: 2`, etc.). For pre-loop agents (JD Extractor, Gatekeeper, Strategist, Title Optimizer), use `"loop_iteration": 0`.
2. **Every finding must have an error_code.** No vague observations.
3. **Every claim must cite evidence.** Quote the specific resume text AND the master resume text.
4. **Do not re-score dimensions already in `06_deterministic_scores.json`** (Bullet Counts, Tone Compliance Deterministic, Surface Match, Semantic Fact-Checking, Metric Fidelity). Focus on what deterministic checks cannot: reasoning quality, strategic relevance, and semantic accuracy.
4. **Use only whole-number scores on a 1–5 scale.** No floats like 3.5. The definitions below are exhaustive — if your evidence maps to a 3, score 3.
5. **If you find no issues for an agent, still emit a finding** with score 5.0 and notes = "No issues found."

---

### Universal Rule: GIGO (Garbage In, Garbage Out) Isolation

**Do not penalize any agent for errors that originated upstream.** An agent is scored solely on how faithfully and correctly it handled the inputs it received.

| Upstream error | Who to penalize |
|---|---|
| JD Extractor hallucinates a requirement | JD Extractor only |
| Gatekeeper inflates a match score | Gatekeeper only |
| Strategist pulls a weak bullet | Strategist only |
| Builder faithfully uses a bad priority map bullet | Do NOT penalize builder |
| Critique sub-agent issues a bad flag | Sub-agent only; do NOT penalize Chief for synthesising it |

---

### LLM-as-a-Judge Scoring Matrix

**1. JD Extractor — dimensions: EX-001, EX-002, EX-003**

| Score | Criteria |
|---|---|
| **5** | Perfect extraction. All implicit requirements caught; all priority assignments match JD document structure. |
| **4** | 1 minor miss (a Low implicit requirement) OR 1 minor priority misalignment (e.g., Medium instead of Low). |
| **3** | Missed multiple Low/Medium requirements OR 1 High-priority requirement misclassified. |
| **2** | Missed a HIGH-priority requirement entirely OR fabricated a requirement not in the JD. |
| **1** | Critical failure: completely false requirements generated OR entire JD context missed. |

**2. Fit Gatekeeper — dimensions: GK-001 through GK-005**

| Score | Criteria |
|---|---|
| **5** | Accurate match strengths in both directions (no inflation, no deflation), no gap credit given, correct GO/NO-GO verdict. |
| **4** | 1 minor grade calibration error (inflation or deflation) on a Low/Medium requirement with no verdict impact. |
| **3** | 1 significant grade calibration error on any requirement OR gap credit given on a non-core item. |
| **2** | Gap credit given on a HIGH requirement OR severe grade mismatch (e.g., `perfect` for `weak`/None evidence, or vice versa). |
| **1** | Verdict failure (False GO or False NO-GO) OR systemic match blindness/fabrication across the profile. |

**3. Strategist — dimensions: ST-001 through ST-004**

| Score | Criteria |
|---|---|
| **5** | Strongest bullets assigned to highest-priority requirements; combination directives provided wherever needed. |
| **4** | Marginally better bullet could have been chosen for one Low/Medium requirement. |
| **3** | 1 clear priority inversion on a HIGH requirement OR missing directive when bullets span different domains/roles. |
| **2** | Multiple priority inversions OR pulled bullets the Gatekeeper explicitly marked `weak` for a HIGH requirement. |
| **1** | Complete misalignment with the JD story; evidence selection appears random. |

**4. Title Optimizer — dimensions: TO-001 through TO-004**

| Score | Criteria |
|---|---|
| **5** | Accurate seniority and function; titles traceable to documented work; no function drift. |
| **4** | Slightly awkward phrasing but functionally and hierarchically accurate. |
| **3** | Minor seniority deflation (e.g., dropping a qualifier like "Senior") OR slight function drift on a secondary role. |
| **2** | Severe seniority deflation (e.g., removing Founder/Co-Founder) OR clear function mismatch on any role. |
| **1** | Seniority inflation (e.g., Coordinator → Director) OR deceptive rewriting to match target JD title. |

**5. Builder — dimensions: BL-001 through BL-010**

> Apply GIGO Isolation: only penalize errors the Builder introduced on its own. If a Priority Map bullet is already wrong, trace the error to Gatekeeper/Strategist.

| Score | Criteria |
|---|---|
| **5** | Fully faithful to Priority Map and master resume. No builder-originated hallucination; combination directives executed. |
| **4** | Minor unnatural phrasing or slight chronological ambiguity; all facts traceable to inputs. |
| **3** | 1 moderate scope inflation initiated by the Builder OR mild gap papering on a Low requirement. |
| **2** | Ignored a mandatory Strategist combination_directive OR major gap papering on a High requirement. |
| **1** | Fabricated content (claim or capability) not found in the Priority Map or master resume. |

**6. Hallucination Checker (Critique Swarm sub-agent) — dimension: CR-001, CR-002**

| Score | Criteria |
|---|---|
| **5** | Caught all unsupported claims; zero false flags on clearly evidenced content. |
| **4** | Missed 1 very subtle hallucination OR issued 1 false flag on borderline phrasing. |
| **3** | Missed a clear hallucination in the Professional Experience OR issued multiple false flags causing noisy revisions. |
| **2** | False-passed a fabricated capability claim (e.g., "SaaS experience", "webinars") in the Summary or Competencies. |
| **1** | Systematic false-pass: major fabrications survived all loops unchallenged. |

**7. Tone & Language Cop (Critique Swarm sub-agent) — dimension: CR-001, CR-002**

| Score | Criteria |
|---|---|
| **5** | Correctly flagged all hero language and corporate-speak; zero false flags on acceptable action verbs. |
| **4** | Missed 1 minor tone issue OR issued 1 false flag on an acceptable but borderline verb. |
| **3** | Missed a clearly banned hero word OR flagged a neutral verb (e.g., "managed") as overclaiming. |
| **2** | Missed multiple hero words OR flagged so many acceptable verbs that revision was materially damaged. |
| **1** | Failed to issue any tone findings on an obviously flowery, AI-sounding draft. |

**8. ATS Keyword Scanner (Critique Swarm sub-agent) — dimension: CR-001, CR-002**

| Score | Criteria |
|---|---|
| **5** | Correctly flagged only missing keywords for skills the candidate actually has; did not flag genuine gaps as missing. |
| **4** | 1 minor erroneous flag (flagged a keyword that was present under a slightly different phrasing). |
| **3** | Flagged a genuine skills gap as a missing keyword (creating hallucination pressure on the Reviser). |
| **2** | Multiple false gap flags OR completely missed a high-priority keyword that the candidate genuinely has. |
| **1** | Flagged skills the candidate has never held, causing systemic fabrication across revision loops. |

**9. Chief Critique — dimensions: CR-004, CR-005**

> Apply GIGO Isolation: if a sub-agent issued a bad flag, score that sub-agent. Only penalize the Chief for how it *synthesised* what it received.

| Score | Criteria |
|---|---|
| **5** | Correctly synthesised sub-agent flags; followed Hallucination > Tone > Formatting > ATS hierarchy; issued valid overall verdict. |
| **4** | Synthesis was correct but the summary reasoning note was confusing or unhelpful (verdict was still valid). |
| **3** | Mild mis-categorisation of one flag's severity, but final verdict was unaffected. |
| **2** | Explicitly violated the resolution hierarchy (e.g., elevated ATS over a Hallucination flag). |
| **1** | Issued `submission_ready` while Blocker-severity flags were still active in its own flag list. |

**10. Reviser — dimensions: CR-003**

> Apply GIGO Isolation: if the Chief issued a bad instruction, score the Chief. Only penalize the Reviser for how it executed the instructions it received.

| Score | Criteria |
|---|---|
| **5** | Addressed all Chief Critique flags precisely without introducing any new errors. |
| **4** | Addressed all flags but produced slightly stilted phrasing in 1–2 bullets. |
| **3** | Failed to fully address 1 valid flag, leaving a partial issue unresolved. |
| **2** | Introduced a new regression (fixed one problem but broke another). |
| **1** | Fabricated new content to bypass a flag constraint (e.g., invented experience to clear an ATS blocker). |
