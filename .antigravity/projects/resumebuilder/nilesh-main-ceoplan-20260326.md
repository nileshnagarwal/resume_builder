# CEO Execution Plan: Resume Builder & Matching Engine

## Mode: Selective Expansion
We are building the core 10-Agent Resume Pipeline, plus introducing an **Outreach Agent** to solve the primary conversion bottleneck (ATS filtering due to zero Canadian experience).

---

## 1. Architecture & Data Flow (ASCII Diagram)

```text
[JD URL / Text] --------------> (1. JD Extractor) -----------> [Requirements JSON]
                                                                     |
[Master Vector DB] --------+--> (2. Fit Gatekeeper) ---------+--> [Go/No-Go Alert]
                           |                                 |
                           +---------------------------------+--> (3. Strategist) ---> [Priority Map]
                                                                     |
                                                          (4. The Chief Builder) ----> [V1 Draft Resume]
                                                                     |
                      +----------------------------------------------+----------------------------------+
                      |                                                                                 |
           (5. The Critique Swarm - Parallel)                                                  (9. Outreach Agent)
           a) Hallucination Checker  b) Tone & Language Cop                                 - Scrape Company LinkedIn
           c) Formatting Inspector   d) ATS Keyword Scanner                                 - Identify Hiring Manager
                      |                                                                     - Draft 3-sentence email
             (6. Chief Critique)                                                                        |
                      |                                                                                 |
      +<====== [Diff Log & Verdict]                                                                     |
      |               |                                                                                 |
      |         (7. Reviser) ================================================================> [Final Submission Ready] 
      |               |                                                                          + [Cold Email Draft]
   [If not ready, loop back to                              
    Critique Swarm up to 3x]
                      |
                      v
             (8. Updater Agent)
             *Asks user for missing context*
             *Writes new context to Master DB*
```

---

## 2. Error & Rescue Map (Zero Silent Failures)

Every system fails. Here is how we rescue the pipeline when it breaks:

| Component | Failure Mode | Rescue Path |
| :--- | :--- | :--- |
| **JD Extractor** | URL blocked by Cloudflare/Bot-protection | Throw `ScrapeError` -> Fallback: Ask user to paste JD text directly. |
| **Master DB** | JD asks for a skill entirely missing from DB | Throw `MissingSkillError` -> Pause pipeline. Updater Agent prompts user via CLI: "Do you have experience with X?" -> If yes, append to DB and resume. |
| **Critique Swarm** | Conflicting feedback (e.g., ATS agent wants keyword X, Tone agent bans it) | Pass to Chief Critique. Chief Critique resolves via built-in hierarchy (Tone > ATS). |
| **Outreach Agent** | Cannot identify exact hiring manager | Throw `NoManagerFound` -> Fall back to generic "Recruiting Team" alias, flag email draft for manual review. |
| **Reviser** | Output resume exceeds 2 pages (token limit slip) | Throw `LengthViolation` -> Force truncate oldest/irrelevant bullets and re-run Formatting Inspector. |

---

## 3. Security & Threat Model
- **Data Privacy:** User's Master Resume contains PII (email, phone, addresses). 
  - *Threat:* Accidental leakage via LLM logging.
  - *Mitigation:* System must run entirely locally (using a local framework like LangChain/LangGraph). API calls strictly to trusted providers (OpenAI/Anthropic) with zero-retention policies.
- **Input Validation:** User pasting malicious or broken JSON in the CLI. 
  - *Mitigation:* Strict Pydantic models for all agent inputs/outputs. Pipeline crashes gracefully if input is malformed.

---

## 4. Scope Definitions

### IN SCOPE (Phase 1 Execution)
- LangGraph / PydanticAI orchestration for exactly the 9 agents mapped above.
- Local vector database (ChromaDB or FAISS) for the Master Profile.
- Automated Diff formatting and JSON structured outputs.
- Basic CLI interface for the user to chat with the Updater Agent.
- **Gap Mitigation (The Modern Cover Letter):** The Outreach Agent will pull "unmatched requirements" from the Fit Gatekeeper and use them to draft a short cold email that directly addresses the "elephant in the room," bypassing the need for a traditional attached cover letter document.

### OUT OF SCOPE (For Now)
- **Web UI / SaaS Dashboard:** Do not build a React frontend yet. The CLI is faster and safer for proving the pipeline.
- **Two-Sided Matching Dashboard:** We are not building the recruiter-facing side yet until we have proven the pipeline works for the candidate (you).
- **PDF Generation:** LLMs are terrible at PDF formatting. The pipeline will output a clean Markdown file. The user will compile it to PDF using an existing tool (like Pandoc or a Markdown-to-PDF web app).

---

## 5. Dream State Delta
**Where we are going (12 Months):** A fully automated background daemon that scans LinkedIn, generates the resume, drafts the email, and sends it automatically without you lifting a finger. 
**What we are building now (1 Week):** A human-in-the-loop CLI tool where you approve the drafts before sending.

---

## 6. Review Readiness Dashboard
- [x] Problem validated
- [x] Moat defined (Master Profile update loop)
- [x] Architecture Diagram complete
- [x] Error Map complete
- [x] Out-of-Scope boundaries locked

**Status:** READY FOR ENGINEERING PLAN (`/plan-eng-review`)
