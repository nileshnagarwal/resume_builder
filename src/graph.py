"""LangGraph pipeline orchestration for the Resume Builder."""

from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.builder import draft_resume
from src.agents.chief_critique import synthesize_critique
from src.agents.critique_swarm import run_critique_swarm
from src.agents.fit_gatekeeper import assess_fit
from src.agents.jd_extractor import extract_requirements
from src.agents.reviser import revise_resume
from src.agents.strategist import build_priority_map
from src.agents.title_optimizer import optimize_titles
from src.agents.updater import prompt_for_missing_context, update_master_resume
from src.validators import validate_bullet_counts
from src.config import MAX_REVISION_LOOPS, OUTPUT_DIR
from src.models import (
    CritiqueFlag,
    CritiqueVerdict,
    DiffEntry,
    DraftResume,
    FitResult,
    JDRequirement,
    PipelineState,
    PriorityMap,
    Severity,
    SubmissionVerdict,
)
from src.vector_db import load_master_resume


# --- State Schema ---
# TypedDict ensures LangGraph correctly merges partial state updates.

class GraphState(TypedDict, total=False):
    jd_text: str
    master_resume_text: str
    requirements: list
    fit_result: Any
    priority_map: Any
    current_draft: Any
    critique_flags: list
    critique_verdict: Any
    diff_log: list
    loop_count: int
    final_resume_md: str


# --- Node Functions ---
# Each node takes a GraphState dict and returns partial state updates.


def node_extract_jd(state: dict) -> dict:
    """Extract requirements from the job description."""
    print("\n🔍 [1/8] Extracting JD requirements...")
    requirements = extract_requirements(state["jd_text"])
    print(f"   Found {len(requirements)} requirements")
    for r in requirements:
        print(f"   - [{r.priority.value}] {r.name}")
    return {"requirements": requirements}


def node_check_fit(state: dict) -> dict:
    """Assess fit between JD requirements and master resume."""
    print("\n📊 [2/8] Assessing fit...")
    master_resume_text = state.get("master_resume_text", "")
    if not master_resume_text:
        master_resume_text = load_master_resume()

    fit_result = assess_fit(state["requirements"], master_resume_text)
    print(f"   Coverage: {fit_result.coverage_pct}%")
    print(f"   Go/No-Go: {'✅ GO' if fit_result.go else '❌ NO-GO'}")
    print(f"   Recommendation: {fit_result.recommendation}")

    if fit_result.unmatched:
        print(f"   ⚠️  Unmatched: {', '.join(fit_result.unmatched)}")

    return {
        "fit_result": fit_result,
        "master_resume_text": master_resume_text,
    }


def node_update_context(state: dict) -> dict:
    """Ask user about unmatched requirements and update the master resume DB."""
    fit_result = state["fit_result"]
    if not fit_result.unmatched:
        return {}

    updates = prompt_for_missing_context(fit_result.unmatched)
    if updates:
        count = update_master_resume(updates)
        print(f"\n✅ Added {count} new entries to master resume DB")

    return {}


def node_build_strategy(state: dict) -> dict:
    """Build the priority map linking requirements to resume evidence."""
    print("\n🎯 [3/8] Building priority map...")
    priority_map = build_priority_map(
        state["requirements"],
        state["fit_result"],
        state["master_resume_text"],
        jd_text=state.get("jd_text", ""),
    )
    print(f"   Mapped {len(priority_map.entries)} requirements to evidence")
    return {"priority_map": priority_map}


def node_optimize_titles(state: dict) -> dict:
    """Optimize historical role titles for ATS alignment."""
    print("\n🏷️  [3.5/8] Optimizing role titles...")
    titles = optimize_titles(
        jd_text=state.get("jd_text", ""),
        priority_map=state["priority_map"],
        master_resume_text=state["master_resume_text"],
    )
    # Attach optimized titles to the priority map
    priority_map = state["priority_map"]
    priority_map.optimized_role_titles = titles
    for t in titles:
        if t.original_title != t.optimized_title:
            print(f"   {t.original_title} → {t.optimized_title}")
        else:
            print(f"   {t.original_title} (unchanged)")
    return {"priority_map": priority_map}


def _check_bullet_counts(draft_text: str, label: str) -> None:
    """Run the programmatic bullet counter and print violations."""
    violations = validate_bullet_counts(draft_text)
    if violations:
        print(f"\n   ⚠️  BULLET COUNT VIOLATIONS ({label}):")
        for v in violations:
            print(f"      {v.message}")
    else:
        print(f"   ✅ Bullet counts valid ({label})")


def node_draft_resume(state: dict) -> dict:
    """Draft the resume from the priority map."""
    loop_count = state.get("loop_count", 0)
    version = loop_count + 1
    print(f"\n✍️  [4/8] Drafting resume V{version}...")

    critique_feedback = ""
    if state.get("critique_verdict"):
        verdict = state["critique_verdict"]
        critique_feedback = verdict.summary + "\n"
        for c in verdict.changes_recommended:
            critique_feedback += (
                f"- @ {c.location}: Remove '{c.removed}' → "
                f"Add '{c.added}' ({c.reason})\n"
            )

    current_draft = draft_resume(
        state["priority_map"],
        state["master_resume_text"],
        version=version,
        critique_feedback=critique_feedback,
    )
    print(f"   Draft V{version} generated ({len(current_draft.full_text)} chars)")
    _check_bullet_counts(current_draft.full_text, f"V{version}")
    return {"current_draft": current_draft}


def node_run_critique(state: dict) -> dict:
    """Run the critique swarm on the current draft, plus deterministic checks."""
    print(f"\n🔬 [5/8] Running critique swarm (V{state['current_draft'].version})...")
    flags = run_critique_swarm(
        state["current_draft"],
        state["master_resume_text"],
        state["requirements"],
    )

    # Inject programmatic bullet-count violations as blocker flags
    violations = validate_bullet_counts(state["current_draft"].full_text)
    for v in violations:
        flags.append(CritiqueFlag(
            agent_name="formatting_validator",
            severity=Severity.BLOCKER,
            location=v.section,
            issue=v.message,
            suggestion=(
                f"Adjust {v.section} to have between "
                f"{v.expected_min} and {v.expected_max} bullets."
            ),
        ))

    blockers = [f for f in flags if f.severity.value == "blocker"]
    improvements = [f for f in flags if f.severity.value == "improvement"]
    print(f"   Found {len(flags)} flags: {len(blockers)} blockers, {len(improvements)} improvements")
    return {"critique_flags": flags}


def node_synthesize_critique(state: dict) -> dict:
    """Synthesize critique flags into a verdict."""
    print("\n⚖️  [6/8] Synthesizing critique verdict...")
    verdict = synthesize_critique(state["critique_flags"], state["current_draft"])
    print(f"   Verdict: {verdict.verdict.value}")
    print(f"   Summary: {verdict.summary}")
    return {"critique_verdict": verdict}


def node_revise(state: dict) -> dict:
    """Revise the resume based on critique."""
    print(f"\n🔄 [7/8] Revising resume...")
    new_draft, diff_log = revise_resume(
        state["current_draft"],
        state["critique_verdict"],
        state["master_resume_text"],
    )
    loop_count = state.get("loop_count", 0) + 1
    print(f"   Produced V{new_draft.version} with {len(diff_log)} changes")

    # Print the diff log
    if diff_log:
        print("\n   📋 DIFF LOG:")
        for d in diff_log:
            print(f"   - @ {d.location}: '{d.removed}' → '{d.added}' ({d.reason})")

    return {
        "current_draft": new_draft,
        "diff_log": diff_log,
        "loop_count": loop_count,
    }


def node_save_outputs(state: dict) -> dict:
    """Save the final resume to the output directory."""
    print("\n💾 [8/8] Saving outputs...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resume_path = OUTPUT_DIR / "tailored_resume.md"
    resume_path.write_text(state["current_draft"].full_text, encoding="utf-8")
    print(f"   Saved: {resume_path}")

    return {"final_resume_md": state["current_draft"].full_text}


# --- Routing ---


def should_revise_again(state: dict) -> str:
    """Decide whether to loop back for another critique round or finalize."""
    verdict = state.get("critique_verdict")
    loop_count = state.get("loop_count", 0)

    if verdict is None:
        return "save"

    if verdict.verdict == SubmissionVerdict.SUBMISSION_READY:
        print(f"\n✅ Resume is submission-ready after {loop_count} revision(s)!")
        return "save"

    if loop_count >= MAX_REVISION_LOOPS:
        print(f"\n⚠️  Max revision loops ({MAX_REVISION_LOOPS}) reached. Finalizing.")
        return "save"

    print(f"\n🔁 Looping for revision {loop_count + 1}/{MAX_REVISION_LOOPS}")
    return "critique"


# --- Graph Definition ---


def build_pipeline() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("extract_jd", node_extract_jd)
    graph.add_node("check_fit", node_check_fit)
    graph.add_node("update_context", node_update_context)
    graph.add_node("build_strategy", node_build_strategy)
    graph.add_node("optimize_titles", node_optimize_titles)
    graph.add_node("draft_resume", node_draft_resume)
    graph.add_node("run_critique", node_run_critique)
    graph.add_node("synthesize_critique", node_synthesize_critique)
    graph.add_node("revise", node_revise)
    graph.add_node("save_outputs", node_save_outputs)

    # Linear flow: extract → fit → update → strategy → draft
    graph.set_entry_point("extract_jd")
    graph.add_edge("extract_jd", "check_fit")
    graph.add_edge("check_fit", "update_context")
    graph.add_edge("update_context", "build_strategy")
    graph.add_edge("build_strategy", "optimize_titles")
    graph.add_edge("optimize_titles", "draft_resume")
    graph.add_edge("draft_resume", "run_critique")
    graph.add_edge("run_critique", "synthesize_critique")
    graph.add_edge("synthesize_critique", "revise")

    # Conditional: after revision, loop or finalize
    graph.add_conditional_edges(
        "revise",
        should_revise_again,
        {
            "critique": "run_critique",
            "save": "save_outputs",
        },
    )

    graph.add_edge("save_outputs", END)

    return graph.compile()
