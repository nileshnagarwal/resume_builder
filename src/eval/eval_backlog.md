# Eval Backlog

Test cases identified during P1/P2 audits that are not yet in the test matrix.
Add these as formal regression tests once the targeted fix has been validated.

---

## EB-001 — Topically-Adjacent Evidence / Role-Framing Mismatch

**Origin:** P2 audit, Bug 1 (HC false CLEAN on "industry-adjacent partner")

**Target agent:** Hallucination Checker (Tier-2 Logical Bridge)

**What it tests:** Whether the HC correctly rejects a draft claim where the
master resume evidence is topically related but describes a structurally
different role relationship. Specifically: evidence says candidate *serves
clients in industry X*, but draft claims candidate *serves other businesses
operating in industry X* (i.e., provider vs. partner-to-providers).

**Proposed JD:** A B2B SaaS company seeking a sales rep who sells *to*
logistics companies (i.e., the candidate would be an industry-adjacent advisor
to logistics providers — a real role flip from the master resume where the
candidate IS the logistics provider).

**Proposed master resume input:** Nilesh's standard master resume (direct
logistics operator to manufacturing clients).

**Expected failure mode the test must catch:** Builder writes "industry-adjacent
partner advising B2B logistics providers on operational efficiency" using the
Strategist's Industry Knowledge bullets — HC must flag this as a hallucination
because the master resume documents the candidate as *the direct service provider*,
not as a consultant/advisor to service providers.

**Pass criteria:**
- HC Tier-2 scratchpad shows bridge FAILS at Step 2 for the role-framing claim
- HC JSON output contains a `blocker` flag for the fabricated characterization
- Reviser removes or corrects the phrase based on that flag

**Adjacent to:** P2 test case (Metrics vs. Narrative evidence choice)

---

## EB-002 — Tone Cop False Flag on Accurately Hedged Master Resume Metrics

**Origin:** P2 audit, Bug 2 (Tone Cop flagged "approximately $830K" as imprecise)

**Target agent:** Tone & Language Cop

**What it tests:** Whether the Tone Cop correctly distinguishes between
(a) inflated/fabricated imprecision (bad) and (b) accurate hedges that are
present verbatim in the master resume (good — must not be flagged).

**Key test phrases:**
- `"approximately $830K CAD"` — verbatim from master resume, must NOT be flagged
- `"2,000+ transportation assignments"` — verbatim from master resume, must NOT be flagged
- `"~$500 to ~$250K CAD"` — verbatim range from master resume, must NOT be flagged
- `"exceeded $1.2M"` — fabricated, MUST be flagged

**Pass criteria:**
- None of the three verbatim-hedged phrases trigger a Tone Cop flag
- The fabricated metric is flagged as an overclaim

---

## EB-003 — ATS Scanner Genuine Gap vs. Evidence Context Conflation

**Origin:** P2 audit, Bug 3 (ATS flagged "mid-market, enterprise sales" using
B2B logistics clients as evidence)

**Target agent:** ATS Keyword Scanner

**What it tests:** Whether the ATS Scanner's feasibility check correctly
distinguishes between *the candidate has B2B experience* (true) and *the
candidate has enterprise software sales experience* (false). Domain context
must not be conflated with the specific skill keyword.

**Key scenarios:**
- JD requires "SaaS sales experience" — master resume has a "digital freight
  matching startup" (LoadKhoj.com) but no confirmed SaaS model. Must be
  flagged as `GENUINE_GAP`, not `MISSING_KEYWORD`.
- JD requires "enterprise sales cycles" — master resume has logistics
  clients in manufacturing. Must be flagged as `GENUINE_GAP`.
- JD requires "pipeline management" — master resume explicitly documents
  outbound prospecting and account lifecycle. Must be `MISSING_KEYWORD`
  (candidate has the skill, just not the keyword).

**Pass criteria:**
- SaaS and enterprise sales appear in scratchpad as `<GENUINE_GAP>`
- Neither generates a JSON flag for the Reviser
- Pipeline management appears as `<MISSING_KEYWORD>` and generates a flag

---
