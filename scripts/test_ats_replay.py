"""
ATS Scanner Replay — Side-by-Side Comparison

Extracts the exact inputs from the 05_traces.json that the ats_keyword_scanner
saw in each loop, then replays them through the updated checker.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.critique_swarm import _check_ats_keywords
from src.models import DraftResume, JDRequirement

TRACES_PATH = "eval_results/P1_rerun/P1/cowork/05_traces.json"
REQ_PATH = "eval_results/P1_rerun/P1/cowork/01_jd_requirements.json"
MASTER_RESUME_PATH = "eval_results/P1_rerun/P1/cowork/09_master_resume.md"
DIVIDER = "=" * 80
SUBDIV  = "-" * 60

def summarise_old_flags(trace: dict) -> list[str]:
    flags = trace.get("state_after", {}).get("flags", [])
    if not flags:
        return ["(no flags — 0 issues raised)"]
    return [f"[{f.get('severity', '?').upper()}] {f.get('issue', '?')}" for f in flags]

async def replay_loop(loop_iteration: int, draft_text: str, requirements: list, master_resume: str):
    draft = DraftResume(full_text=draft_text, version=loop_iteration + 1, sections=[])
    raw, flags = await _check_ats_keywords(draft, requirements, master_resume)
    return raw, flags

async def main():
    print(f"\n{DIVIDER}\n  ATS KEYWORD SCANNER REPLAY \n{DIVIDER}\n")
    with open(TRACES_PATH) as f: traces = json.load(f)
    with open(REQ_PATH) as f: reqs_raw = json.load(f)
    requirements = [JDRequirement(**r) for r in reqs_raw]
    with open(MASTER_RESUME_PATH) as f: master_resume = f.read()

    agent_traces = [t for t in traces if t.get("agent_name") == "ats_keyword_scanner"]
    if not agent_traces:
        print("ERROR: No ats_keyword_scanner traces found.")
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
            
        raw, new_flags = await replay_loop(loop, draft_text, requirements, master_resume)
        if new_flags:
            for f in new_flags:
                print(f"  [{f.severity.upper()}] {f.issue}")
        else:
            print("  (no flags — 0 issues raised)")
            
        print(f"\n{'REASONING SCRATCHPAD (Summary)':^60}\n{SUBDIV}")
        lines = raw.strip().split("\n")
        # Print lines that look like status since the scratchpad is big
        pd_lines = [l for l in lines if l.startswith("Status:") or l.startswith("<KEYWORD>")]
        for line in pd_lines[:40]:
            print(" ", line)
        if len(pd_lines) > 40: print("  ... [truncated]")

if __name__ == "__main__":
    asyncio.run(main())
