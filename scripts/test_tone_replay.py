"""
Tone Cop Replay — Side-by-Side Comparison

Extracts the exact inputs from the 05_traces.json that the tone_language_cop
saw in each loop, then replays them through the updated checker.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.critique_swarm import _check_tone
from src.models import DraftResume

TRACES_PATH = "eval_results/P1_rerun/P1/cowork/05_traces.json"
DIVIDER = "=" * 80
SUBDIV  = "-" * 60

def summarise_old_flags(trace: dict) -> list[str]:
    flags = trace.get("state_after", {}).get("flags", [])
    if not flags:
        return ["(no flags — 0 issues raised)"]
    return [f"[{f.get('severity', '?').upper()}] {f.get('location', '?')}: {f.get('issue', '?')}" for f in flags]

async def replay_loop(loop_iteration: int, draft_text: str):
    draft = DraftResume(full_text=draft_text, version=loop_iteration + 1, sections=[])
    raw, flags = await _check_tone(draft)
    return raw, flags

async def main():
    print(f"\n{DIVIDER}\n  TONE COP REPLAY \n{DIVIDER}\n")
    with open(TRACES_PATH) as f: traces = json.load(f)

    agent_traces = [t for t in traces if t.get("agent_name") == "tone_language_cop"]
    if not agent_traces:
        print("ERROR: No tone_language_cop traces found.")
        sys.exit(1)

    for trace in sorted(agent_traces, key=lambda t: t.get("loop_iteration", 0)):
        loop = trace.get("loop_iteration", "?")
        draft_text = trace.get("state_before", {}).get("current_draft", "")
        
        print(f"\n{DIVIDER}\n  LOOP {loop}\n{DIVIDER}")
        print(f"\n{'OLD RESULTS (P1_rerun)':^60}\n{SUBDIV}")
        for line in summarise_old_flags(trace): print(" ", line)
        
        print(f"\n{'NEW RESULTS (Updated Checker)':^60}\n{SUBDIV}")
        if not draft_text:
            print("  ERROR: No draft text captured")
            continue
            
        raw, new_flags = await replay_loop(loop, draft_text)
        if new_flags:
            for f in new_flags:
                print(f"  [{f.severity.upper()}] {f.location}")
                print(f"    Issue: {f.issue}")
        else:
            print("  (no flags — 0 issues raised)")
            
        print(f"\n{'REASONING SCRATCHPAD (Summary)':^60}\n{SUBDIV}")
        # The Tone Cop wasn't updated to write a prose scratchpad, it just outputs JSON direct in the prompt
        # We will just print the raw text extracted
        lines = raw.strip().split("\n")[:20]
        for line in lines: print(" ", line)
        if len(raw.strip().split("\n")) > 20: print("  ... [truncated]")


if __name__ == "__main__":
    asyncio.run(main())
