import asyncio
import json
import os
from src.models import DraftResume
from src.agents.critique_swarm import _check_hallucinations

# Paths
TRACES_PATH = "eval_results/P1_rerun/P1/cowork/05_traces.json"
MASTER_RESUME_PATH = "eval_results/P1_rerun/P1/cowork/09_master_resume.md"

async def main():
    # Load master resume
    with open(MASTER_RESUME_PATH, 'r') as f:
        master_text = f.read()

    # Load traces
    with open(TRACES_PATH, 'r') as f:
        traces = json.load(f)

    # Filter hallucination checker traces
    hc_traces = [t for t in traces if t.get('agent_name') == 'hallucination_checker']
    
    print("="*60)
    print("TESTING NEW HALLUCINATION CHECKER ON P1 DRAFTS")
    print("="*60)

    for i, t in enumerate(hc_traces):
        loop_num = t.get('loop_iteration')
        state_before = t.get('state_before', {})
        draft_text = state_before.get('current_draft', "")
        draft_version_str = state_before.get('draft_version', "V1")
        
        # Pydantic expects int for version, so strip the 'V'
        draft_version = int(draft_version_str.replace("V", "")) if isinstance(draft_version_str, str) else draft_version_str
        
        draft = DraftResume(
            full_text=draft_text,
            version=draft_version,
            sections=[]  # Not strictly needed for this test
        )

        print(f"\nEvaluating Loop {loop_num} (Draft {draft_version_str})...")
        try:
            # We wrapped LLM in tenacity, so no 503 should break it (or rather it will retry)
            raw, flags = await _check_hallucinations(draft, master_text)
            
            print(f"\n--- FLAGS FOUND: {len(flags)} ---")
            for f in flags:
                print(f"[{f.severity}] {f.location} - {f.issue}")
                
            print("\n--- REASONING SCRATCHPAD (Excerpt) ---")
            # If scratchpad is long, print the hallucination mentions
            lines = raw.split('\n')
            for line in lines:
                if line.startswith('[HALLUCINATION]') or 'Claimed:' in line or 'Evidence:' in line or 'Reasoning:' in line or 'Severity:' in line:
                    print(line)
                    
        except Exception as e:
            print(f"Error evaluating loop {loop_num}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
