# Walkthrough: Multi-Agent Resume Builder Pipeline

## What Was Built
A complete multi-agent resume tailoring pipeline with 12 Python files focusing on deterministic quality guardrails, validation, and cost-effective modeling.

### Foundation & Constraints
| File | Purpose |
|------|---------|
| [config.py](../../../src/config.py) | Paths, model name, formatting rules, bullet count ranges (Summary, Most Recent, Past roles). |
| [models.py](../../../src/models.py) | 12 Pydantic data contracts between agents, ensuring typed data exchange. |
| [vector_db.py](../../../src/vector_db.py) | ChromaDB wrapper handling the Master Profile. V1 handles ~19k tokens, adhering to the 32K context caching limit. |
| [llm.py](../../../src/llm.py) | Shared Gemini API caller for `gemini-3.1-flash-lite-preview` (text + JSON modes). |
| [validators.py](../../../src/validators.py) | **Zero-cost Deterministic Validator.** Uses regex and formatting structures to strictly enforce bullet limits per section (e.g., max 6 for recent, 3 for past, handling company headers vs titles). Flags violations as `BLOCKER` for the chief critique. |

### Agents
| File | Task |
|------|------|
| [jd_extractor.py](../../../src/agents/jd_extractor.py) | Extract & rank JD requirements. |
| [fit_gatekeeper.py](../../../src/agents/fit_gatekeeper.py) | Go/no-go fit assessment against the master resume. |
| [strategist.py](../../../src/agents/strategist.py) | Maps requirements → STAR bullets, assigning priority and resolving relevance. |
| [builder.py](../../../src/agents/builder.py) | Drafts tailored resume with strict anti-hallucination and anti-semantic drift constraints (defined in `SYSTEM_PROMPT`). |
| [critique_swarm.py](../../../src/agents/critique_swarm.py) | 4 parallel checks: hallucination matching, tone (no hero words), ATS keyword coverage, formatting rules. |
| [chief_critique.py](../../../src/agents/chief_critique.py) | Synthesizes flags → verdict. Resolves Tone vs. ATS conflicts, prioritizing Tone rules over ATS stuffing. |
| [reviser.py](../../../src/agents/reviser.py) | Revises the draft based on critique, up to 3 iterative loops. Produces a detailed diff log. |
| [updater.py](../../../src/agents/updater.py) | Prompts user iteratively for missing context and continuously appends to ChromaDB and the master resume file. |

### Orchestration
| File | Purpose |
|------|---------|
| [graph.py](../../../src/graph.py) | LangGraph state machine orchestrating 9 nodes with a conditional loop to `chief_critique` on failure (max 3 loops). |
| [cli.py](../../../src/cli.py) | CLI entry point with `--jd` and `--reingest` flags. |

## Validation & Architecture Logic
- **Architecture Assumptions Validated:** Built specific handlers for `**PROFESSIONAL EXPERIENCE**` dividers and `**COMPANY | Location**` headers mapping rules in `validators.py`.
- **Pipeline Constraints:** Builder prompt reinforced with rules for "Anti-Drift," "Core Competencies," and strict trace-to-master checking.
- ✅ All imports pass (`python -c "from src.graph import build_pipeline"`)
- ✅ LangGraph pipeline compiles with 9 nodes + conditional loop
- ✅ Model configured: `gemini-3.1-flash-lite-preview`

## How to Run
```bash
export GEMINI_API_KEY="your-key-here"
source venv/bin/activate
python -m src.cli --jd jds/growth_partnerships_condovoter_260326.txt --reingest
```
