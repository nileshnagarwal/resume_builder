"""Eval Harness Runner orchestrating the pipeline and scoring."""

import json
import shutil
import time
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import JD_DIR, MASTER_RESUME_DIR
from src.graph import build_pipeline
from src.eval.test_matrix import EvalPair, get_pairs
from src.eval.scoring import AgentTrace, PairResult, EvalReport
from src.eval.scorers import (
    score_fit_verdict,
    score_bullet_counts,
    score_banned_words,
    score_hallucination_surface,
    score_semantic_similarity,
    score_metric_fidelity,
    score_priority_alignment,
    score_loop_efficiency,
)

# Path to the static eval instructions template for Cowork
_EVAL_INSTRUCTIONS_PATH = Path(__file__).parent / "eval_instructions.md"
_ERROR_TAXONOMY_PATH = Path(__file__).parent / "error_taxonomy.py"


# ---------------------------------------------------------------------------
# State proxy — bridges dict-based LangGraph state to scorer expectations
# ---------------------------------------------------------------------------

def _state_to_obj(state: dict):
    class StateProxy:
        def __init__(self, s):
            self.fit_result = s.get("fit_result")
            self.current_draft = s.get("current_draft")
            self.master_resume_text = s.get("master_resume_text", "")
            self.final_resume_md = s.get("final_resume_md", "")
            self.requirements = s.get("requirements", [])
            self.priority_map = s.get("priority_map")
    return StateProxy(state)


# ---------------------------------------------------------------------------
# Cowork directory writer — replaces generate_claude_prompt()
# ---------------------------------------------------------------------------

def _write_cowork_directory(
    pair: EvalPair,
    final_state: dict,
    scores: list,
    traces: list[AgentTrace],
    loops_to_ready: Optional[int],
    pair_dir: Path,
) -> None:
    """Write the structured Cowork directory for a single eval pair.

    Creates ``pair_dir/cowork/`` with numbered files that Claude Cowork
    can reference autonomously.
    """
    cowork_dir = pair_dir / "cowork"
    cowork_dir.mkdir(parents=True, exist_ok=True)

    # 01 — JD Requirements
    if final_state.get("requirements"):
        reqs = [r.dict() for r in final_state["requirements"]]
        (cowork_dir / "01_jd_requirements.json").write_text(
            json.dumps(reqs, indent=2), encoding="utf-8"
        )

    # 02 — Fit Result
    if final_state.get("fit_result"):
        (cowork_dir / "02_fit_result.json").write_text(
            final_state["fit_result"].model_dump_json(indent=2), encoding="utf-8"
        )

    # 03 — Priority Map
    if final_state.get("priority_map"):
        (cowork_dir / "03_priority_map.json").write_text(
            final_state["priority_map"].model_dump_json(indent=2), encoding="utf-8"
        )

    # 04 — Final Resume
    if final_state.get("final_resume_md"):
        (cowork_dir / "04_final_resume.md").write_text(
            final_state["final_resume_md"], encoding="utf-8"
        )

    # 05 — Full pipeline traces (state_before + state_after per agent per loop)
    (cowork_dir / "05_traces.json").write_text(
        json.dumps([t.to_dict() for t in traces], indent=2), encoding="utf-8"
    )

    # 06 — Deterministic Scores
    (cowork_dir / "06_deterministic_scores.json").write_text(
        json.dumps([s.to_dict() for s in scores], indent=2), encoding="utf-8"
    )

    # 07 — Error Taxonomy (static copy)
    if _ERROR_TAXONOMY_PATH.exists():
        shutil.copy2(_ERROR_TAXONOMY_PATH, cowork_dir / "07_error_taxonomy.py")

    # 08 — Eval Instructions (static copy)
    if _EVAL_INSTRUCTIONS_PATH.exists():
        shutil.copy2(_EVAL_INSTRUCTIONS_PATH, cowork_dir / "08_eval_instructions.md")

    # 09 — Full Master Resume
    resume_path = MASTER_RESUME_DIR / pair.resume_file
    if resume_path.exists():
        shutil.copy2(resume_path, cowork_dir / "09_master_resume.md")


# ---------------------------------------------------------------------------
# Trace analysis helpers
# ---------------------------------------------------------------------------

def _compute_loops_to_ready(traces: list[AgentTrace]) -> Optional[int]:
    """Count revision loops before the first submission_ready verdict.

    Returns None if submission_ready was never reached.
    """
    revise_count = 0
    for t in traces:
        if t.agent_name == "revise":
            revise_count += 1
        if t.agent_name == "synthesize_critique":
            after = t.state_after
            verdict = after.get("critique_verdict")
            if isinstance(verdict, dict):
                v = verdict.get("verdict", "")
            else:
                v = getattr(verdict, "verdict", "")
                v = getattr(v, "value", v) if v else ""
            if str(v) == "submission_ready":
                return revise_count
    return None


# ---------------------------------------------------------------------------
# Core pair processing
# ---------------------------------------------------------------------------

def _process_pair(p: EvalPair, dry_run: bool, score: bool, output_dir: Path) -> PairResult:
    print(f"⏳ [{p.pair_id}] Started evaluating...")
    jd_path = JD_DIR / p.jd_file
    resume_path = MASTER_RESUME_DIR / p.resume_file

    if not jd_path.exists() or not resume_path.exists():
        print(f"❌ [{p.pair_id}] Missing source files")
        return PairResult(p.pair_id, p.category, False, 0.0, error="Missing source files")

    jd_text = jd_path.read_text("utf-8")
    resume_text = resume_path.read_text("utf-8")

    start_t = time.time()
    initial_state = {
        "jd_text": jd_text,
        "master_resume_text": resume_text,
        "requirements": [],
        "fit_result": None,
        "priority_map": None,
        "current_draft": None,
        "critique_flags": [],
        "critique_verdict": None,
        "diff_log": [],
        "loop_count": 0,
        "final_resume_md": "",
        "interactive_mode": False,
        # Enable tracing for full observability
        "_tracing_enabled": True,
        "_traces": [],
    }

    pipeline = build_pipeline()
    try:
        final_state = pipeline.invoke(initial_state)
        elapsed = time.time() - start_t

        # Extract traces
        traces: list[AgentTrace] = final_state.get("_traces", [])
        loops_to_ready = _compute_loops_to_ready(traces)

        fit_go = None
        fit_cov = None
        if final_state.get("fit_result"):
            fit_go = final_state["fit_result"].go
            fit_cov = final_state["fit_result"].coverage_pct

        scores = []
        if score and not dry_run:
            st = _state_to_obj(final_state)
            scores.extend(score_fit_verdict(p.pair_id, p.expected_go, p.expected_coverage_range, st))
            scores.extend(score_bullet_counts(st))
            scores.extend(score_banned_words(st))
            scores.extend(score_hallucination_surface(st))
            scores.extend(score_semantic_similarity(st))
            scores.extend(score_metric_fidelity(st))
            scores.extend(score_priority_alignment(st))
            scores.extend(score_loop_efficiency(traces, loops_to_ready))

        res = PairResult(
            pair_id=p.pair_id,
            category=p.category,
            success=True,
            elapsed_seconds=elapsed,
            fit_go=fit_go,
            fit_coverage=fit_cov,
            agent_scores=scores,
            traces=traces,
            loops_to_ready=loops_to_ready,
        )

        if not dry_run:
            pair_dir = output_dir / p.pair_id
            pair_dir.mkdir(parents=True, exist_ok=True)

            # Legacy individual artifacts (kept for backwards compat)
            if final_state.get("requirements"):
                (pair_dir / "requirements.json").write_text(json.dumps([r.dict() for r in final_state["requirements"]], indent=2))
            if final_state.get("fit_result"):
                (pair_dir / "fit_result.json").write_text(final_state["fit_result"].model_dump_json(indent=2))
            if final_state.get("priority_map"):
                (pair_dir / "priority_map.json").write_text(final_state["priority_map"].model_dump_json(indent=2))
            if final_state.get("final_resume_md"):
                (pair_dir / "final_resume.md").write_text(final_state["final_resume_md"])

            (pair_dir / "scores.json").write_text(json.dumps([s.to_dict() for s in scores], indent=2))

            # Trace log — full state dumps per agent
            (pair_dir / "traces.json").write_text(
                json.dumps([t.to_dict() for t in traces], indent=2)
            )

            # Cowork structured directory
            _write_cowork_directory(p, final_state, scores, traces, loops_to_ready, pair_dir)

        print(f"✅ [{p.pair_id}] Finished in {elapsed:.1f}s (loops_to_ready={loops_to_ready})")
        return res

    except Exception as e:
        elapsed = time.time() - start_t
        print(f"❌ [{p.pair_id}] Error: {e}")
        return PairResult(p.pair_id, p.category, False, elapsed, error=str(e))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_eval(
    category: Optional[str] = None,
    pair_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    score: bool = True,
    output_dir: Optional[Path] = None,
) -> EvalReport:

    pairs = get_pairs(category)
    if pair_ids:
        pairs = [p for p in pairs if p.pair_id.upper() in [pid.upper() for pid in pair_ids]]

    if not output_dir:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output_dir = Path("eval_results") / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)

    report = EvalReport(
        timestamp=datetime.now().isoformat(),
        results=[]
    )

    print(f"\n🚀 Running EVAL HARNESS concurrently on {len(pairs)} pairs")
    if dry_run:
        print("   [DRY RUN MODE - purely for inspection]")

    futures = []
    # 5 workers handles rate limits well while speeding up execution roughly 5x
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for p in pairs:
            futures.append(executor.submit(_process_pair, p, dry_run, score, output_dir))

        for future in concurrent.futures.as_completed(futures):
            report.results.append(future.result())

    # Sort results by pair ID for deterministic summary output
    report.results.sort(key=lambda r: r.pair_id)

    if not dry_run:
        (output_dir / "summary.json").write_text(json.dumps(report.to_dict(), indent=2))
        _print_summary(report, output_dir)

    return report


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(report: EvalReport, output_dir: Path):
    table = "EVALUATION SUMMARY\n====================\n\n"
    table += f"Timestamp: {report.timestamp}\n\n"
    table += f"{'ID':<5} | {'Category':<15} | {'Success':<8} | {'GO':<6} | {'Cov %':<6} | {'Loops':<6} | {'Scores':<8} | {'Time (s)'}\n"
    table += "-" * 90 + "\n"

    for r in report.results:
        go_str = "GO" if r.fit_go else "NO-GO" if r.fit_go is False else "N/A"
        cov_str = f"{r.fit_coverage:.1f}" if r.fit_coverage else "N/A"
        loops_str = str(r.loops_to_ready) if r.loops_to_ready is not None else "N/A"
        score_ct = len(r.agent_scores)
        succ = "PASS" if r.success else "FAIL"
        err_msg = f" ({r.error})" if r.error else ""
        table += f"{r.pair_id:<5} | {r.category:<15} | {succ:<8} | {go_str:<6} | {cov_str:<6} | {loops_str:<6} | {score_ct:<8} | {r.elapsed_seconds:.1f}{err_msg}\n"

    print("\n\n" + table)
    (output_dir / "summary.txt").write_text(table)
    print(f"\n💾 Full results saved to: {output_dir}")
