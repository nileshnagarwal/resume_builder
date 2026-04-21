"""
Hallucination Checker Replay — P1 Side-by-Side Comparison

Extracts the exact draft inputs from the P1_rerun 05_traces.json that the
hallucination_checker saw in each loop, then replays them through the updated
checker. Outputs a side-by-side comparison of old vs. new flags per loop.

Usage:
    GEMINI_API_KEY=<key> python scripts/test_hallucination_replay.py
"""

import asyncio
import json
import os
import sys
import textwrap

# Allow imports from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.critique_swarm import _check_hallucinations
from src.models import DraftResume

TRACES_PATH = "eval_results/P1_rerun/P1/cowork/05_traces.json"
MASTER_RESUME_PATH = "eval_results/P1_rerun/P1/cowork/09_master_resume.md"

DIVIDER = "=" * 80
SUBDIV  = "-" * 60


def load_inputs():
    """Load the hallucination_checker state_before entries from P1_rerun traces."""
    with open(TRACES_PATH) as f:
        traces = json.load(f)

    with open(MASTER_RESUME_PATH) as f:
        master_resume = f.read()

    hc_traces = [t for t in traces if t.get("agent_name") == "hallucination_checker"]
    hc_traces.sort(key=lambda t: t.get("loop_iteration", 0))
    return hc_traces, master_resume


def summarise_old_flags(trace: dict) -> list[str]:
    """Return old flag descriptions from the trace's state_after."""
    flags = trace.get("state_after", {}).get("flags", [])
    if not flags:
        return ["(no flags — 0 issues raised)"]
    return [f"[{f.get('severity', '?').upper()}] {f.get('location', '?')}: {f.get('issue', '?')}" for f in flags]


async def replay_loop(loop_iteration: int, draft_text: str, master_resume: str):
    """Run the updated hallucination checker on a single draft."""
    from src.llm import call_llm
    from src.agents.critique_swarm import HALLUCINATION_PROMPT, _extract_json_from_response, _parse_flags

    draft = DraftResume(
        full_text=draft_text,
        version=loop_iteration + 1,
        sections=[],
    )
    user_prompt = (
        f"## Resume Draft\n{draft.full_text}\n\n"
        f"## Master Resume\n{master_resume}"
    )
    raw = call_llm(system_prompt=HALLUCINATION_PROMPT, user_prompt=user_prompt)
    json_text = _extract_json_from_response(raw)
    flags = _parse_flags(json_text, "hallucination_checker")
    return raw, flags


async def main():
    print(f"\n{DIVIDER}")
    print("  HALLUCINATION CHECKER REPLAY — P1 Side-by-Side")
    print(f"{DIVIDER}\n")

    hc_traces, master_resume = load_inputs()

    if not hc_traces:
        print("ERROR: No hallucination_checker traces found in", TRACES_PATH)
        sys.exit(1)

    print(f"Found {len(hc_traces)} hallucination_checker loops to replay.\n")

    for trace in hc_traces:
        loop = trace.get("loop_iteration", "?")
        draft_text = trace.get("state_before", {}).get("current_draft", "")
        draft_version = trace.get("state_before", {}).get("draft_version", "?")

        print(f"\n{DIVIDER}")
        print(f"  LOOP {loop}  |  Draft: {draft_version}")
        print(DIVIDER)

        # --- OLD RESULTS ---
        print(f"\n{'OLD RESULTS (P1_rerun)':^60}")
        print(SUBDIV)
        for line in summarise_old_flags(trace):
            print(" ", line)

        # --- NEW RESULTS ---
        print(f"\n{'NEW RESULTS (Updated Checker)':^60}")
        print(SUBDIV)

        if not draft_text:
            print("  ERROR: No draft text captured in state_before for this loop.")
            continue

        raw, new_flags = await replay_loop(loop, draft_text, master_resume)

        if new_flags:
            for f in new_flags:
                print(f"  [{f.severity.upper()}] {f.location}")
                print(f"    Issue: {f.issue}")
                if hasattr(f, 'suggestion') and f.suggestion:
                    print(f"    Fix:   {f.suggestion}")
        else:
            print("  (no flags — 0 issues raised)")

        # --- RAW SCRATCHPAD ---
        print(f"\n{'REASONING SCRATCHPAD (first 40 lines)':^60}")
        print(SUBDIV)
        lines = raw.strip().split("\n")[:40]
        for line in lines:
            print(" ", line)
        if len(raw.strip().split("\n")) > 40:
            print("  ... [scratchpad truncated — see full output in 05_traces.json]")

    print(f"\n{DIVIDER}")
    print("  REPLAY COMPLETE")
    print(DIVIDER)


if __name__ == "__main__":
    asyncio.run(main())
