# Implementation Plan: Multi-Agent Resume Builder Pipeline

## Goal
Build a multi-agent resume tailoring pipeline that takes a JD and a Master Resume, runs a Builder→Critique loop (up to 3 iterations), and outputs a submission-ready resume. All agents use `gemini-3.1-flash-lite-preview` to start; we can swap in stronger models per-agent later if quality requires it.

## What Already Exists
- **ChromaDB data** at `data/chroma_db/` (pre-populated vector store)
- **Master Resume** at `master_resumes/Nilesh_Agarwal_Master_Resume_20260323.md`
- **Builder & Critique instruction prompts** at root (`Resume_Builder_Instructions_20260320.txt`, `Resume_Critique_Instructions_20260320.txt`)
- **Sample JD** at `jds/growth_partnerships_condovoter_260326.txt`
- **Fully functioning src/ directory** (Agents, models, orchestration graph, and validators are coded and running)
- **Sample output** at `output/tailored_resume.md`

## NOT In Scope
- Web UI / React frontend
- Recruiter-side matching dashboard
- PDF generation (output is Markdown)
- Outreach / cold email agent (Deferred to Phase 2. We must finalize the Eval Engine and model benchmarks first.)

---

## Proposed Changes

### Core Models & Config

#### [NEW] [config.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/config.py)
- Central configuration: API keys (from env vars), model name (`gemini-3.1-flash-lite-preview` for all agents), ChromaDB path, max revision loops (3), output directory.

#### [NEW] [models.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/models.py)
- Pydantic models for all inter-agent data contracts:
  - `JDRequirement(name, description, priority, keywords[])`
  - `FitResult(go: bool, coverage_pct, matched[], unmatched[], recommendation)`
  - `PriorityMapEntry(requirement, priority, master_resume_bullets[], rationale)`
  - `PriorityMap(entries[], suggested_job_title)`
  - `DraftResume(version, sections[], full_text)`
  - `CritiqueFlag(agent_name, severity, location, issue, suggestion)`
  - `DiffEntry(location, removed, added, reason)`
  - `CritiqueVerdict(verdict: enum, flags[], changes_recommended[], summary)`
  - `PipelineState` (the LangGraph state object carrying all of the above plus textual inputs and outputs)

---

### Agent Implementations

#### [NEW] [agents/jd_extractor.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/jd_extractor.py)
- Extracts requirements from JD text, outputs `list[JDRequirement]`.

#### [NEW] [agents/fit_gatekeeper.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/fit_gatekeeper.py)
- Compares `JDRequirement[]` against ChromaDB. Outputs `FitResult` with matched/unmatched arrays.

#### [NEW] [agents/strategist.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/strategist.py)
- Builds `PriorityMap` by semantically matching JD requirements to the best STAR bullets in the master resume.

#### [NEW] [agents/builder.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/builder.py)
- Drafts V1 resume using `PriorityMap` + Builder instruction prompt. Outputs `DraftResume`.

#### [NEW] [agents/critique_swarm.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/critique_swarm.py)
- **Contains 3 Mini sub-agents**, each returning `CritiqueFlag[]`:
  - `hallucination_checker()` — compares draft claims against master resume text
  - `tone_language_cop()` — checks for banned hero words, tense violations
  - `ats_keyword_scanner()` — checks keyword coverage from `JDRequirement[]`
- All run via `asyncio.gather()` for parallel execution.

#### [NEW] [validators.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/validators.py)
- Programmatic, deterministic code validator that runs after every draft to enforce exact bullet counts (0 API cost). Injects formatting failure violations as `Severity.BLOCKER` into the critique swarm's flags.

#### [NEW] [agents/chief_critique.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/chief_critique.py)
- Ingests all `CritiqueFlag[]` from the swarm, resolves conflicts (Tone > ATS hierarchy), checks job title alignment, outputs `CritiqueVerdict`.

#### [NEW] [agents/reviser.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/reviser.py)
- Takes `CritiqueVerdict` + current `DraftResume`, states agreement/disagreement, produces revised `DraftResume` + `DiffEntry[]`.

#### [NEW] [agents/updater.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/agents/updater.py)
- If `FitResult.unmatched` contains items, prompts user via CLI. Appends confirmed new info to ChromaDB and master resume file.

---

### Pipeline Orchestration

#### [NEW] [graph.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/graph.py)
- LangGraph `StateGraph` definition with:
  - Nodes: `extract_jd` → `check_fit` → `build_strategy` → `draft_resume` → `run_critique_swarm` → `synthesize_critique` → `revise`
  - Conditional edge after `revise`: if `verdict != SUBMISSION_READY and loop_count < 3`, route back to `run_critique_swarm`
  - Terminal node: `save_outputs` (writes `output/tailored_resume.md`)

#### [NEW] [vector_db.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/vector_db.py)
- Wrapper around ChromaDB: `load_master_resume()`, `query_similar(text, n)`, `add_entry(text, metadata)`. Uses existing `data/chroma_db/`.

---

### CLI Entry Point

#### [NEW] [cli.py](file:///Users/nileshagarwal/Coding%20Projects/ResumeBuilder/src/cli.py)
- `python -m src.cli --jd <path> [--master-resume <path>]`
- Loads JD text, initializes `PipelineState`, runs the graph, prints progress, saves outputs.

---

## Model Configuration

All agents use **`gemini-3.1-flash-lite-preview`** to start. This keeps costs minimal while we validate the pipeline logic. Once the pipeline is working end-to-end, we can selectively upgrade individual agents (Strategist, Builder, Chief Critique, Reviser) to a Pro model if quality requires it.

| # | Agent | Task Type |
|---|-------|-----------|
| 1 | JD Extractor | Extraction |
| 2 | Fit Gatekeeper | Comparison |
| 3 | Strategist | Semantic matching |
| 4 | Chief Builder | Prose synthesis |
| 5a | Hallucination Checker | Factual comparison |
| 5b | Tone & Language Cop | Pattern matching |
| 5c | Formatting Inspector | Counting rules |
| 5d | ATS Keyword Scanner | Keyword matching |
| 6 | Chief Critique | Conflict resolution |
| 7 | Reviser | Creative rewriting |
| 8 | Updater | Data append |

---

## Verification Plan

### Automated Tests

> [!IMPORTANT]
> No existing tests were found in the codebase. We will create a `tests/` directory.

1. **Unit Tests** (`tests/test_models.py`)
   - Validate all Pydantic models accept valid data and reject malformed data.
   - Run: `python -m pytest tests/test_models.py -v`

2. **Unit Tests** (`tests/test_agents.py`)
   - Mock the LLM API calls. Verify each agent function accepts the correct input model and returns the correct output model.
   - Run: `python -m pytest tests/test_agents.py -v`

3. **Integration Test** (`tests/test_graph.py`)
   - Mock all LLM calls. Run the full LangGraph pipeline with a sample JD and master resume. Verify:
     - The graph executes all nodes in order
     - The conditional loop triggers correctly when verdict is not submission-ready
     - The loop terminates after max 3 iterations
   - Run: `python -m pytest tests/test_graph.py -v`

### Manual Verification (End-to-End Smoke Test)
1. Run: `python -m src.cli --jd jds/growth_partnerships_condovoter_260326.txt`
2. Verify `output/tailored_resume.md` is generated with correct sections
3. Verify the CLI prints the Diff Log for each revision iteration
5. Verify the pipeline completes in under 5 minutes

### Dependencies to Install
```bash
pip install langgraph langchain-google-genai pydantic pytest
```
(chromadb, google-genai, anthropic already in venv)

---

## V2 Future Architecture (Post-V1)

*This section captures high-leverage architectural upgrades deferred until V1 is stable.*

### 1. Master Profile as a Knowledge Graph (Wiki)
**The Concept:** Instead of dumping raw markdown text into ChromaDB and using standard vector retrieval, we restructure the Master Profile into a localized Knowledge Graph or unstructured Wiki.
*   **Nodes:** Roles, Projects, Skills, Core Competencies, Companies.
*   **Edges:** "Utilized [Skill] at [Role]", "Demonstrated [Core Competency] via [Project]".
*   **Why it matters:** In V1, if a JD asks for "Leadership," vector retrieval grabs the bullets that sound most like leadership. In a Knowledge Graph, the LLM can traverse relationships: "The JD wants Leadership. Let me query the `[Leadership]` node to see all linked `[Project]` nodes, then pull the specific `[Skill]` nodes attached to those projects to write the perfect bullet."
*   **Impact:** Dramatically improves the Strategist agent's ability to map the *right* evidence to complex, multi-layered JD requirements.

### 2. Provider-Level Prompt Caching
See the `root_cause_analysis.md` economics breakdown. Switch to a provider with low minimum-token caching thresholds (like Anthropic) or wait until the Master Profile surpasses Gemini's 32K minimum to achieve ~60% cost reductions per run.
