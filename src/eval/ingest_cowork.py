"""Ingestion script to merge Cowork results with deterministic scores."""

import json
import argparse
from pathlib import Path


def ingest_cowork_results(pair_dir: Path, cowork_json_name: str = "cowork_results.json"):
    """Merge determinisic scores with Cowork JSON and print a unified view."""
    
    scores_path = pair_dir / "scores.json"
    cowork_path = pair_dir / cowork_json_name
    
    if not scores_path.exists():
        print(f"❌ Missing {scores_path.name}. Did the eval harness finish successfully?")
        return
        
    if not cowork_path.exists():
        print(f"❌ Missing {cowork_path.name}. Please save the Cowork JSON output here:\n  {cowork_path}")
        return
        
    # 1. Load Local Deterministic Scores
    local_scores = json.loads(scores_path.read_text("utf-8"))
    
    # 2. Load Cowork Results
    try:
        cowork_results = json.loads(cowork_path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {cowork_json_name}: {e}")
        return
        
    # Normalize cowork_results (ensure it's a list)
    if isinstance(cowork_results, dict):
        if "findings" in cowork_results:
            cowork_results = cowork_results["findings"]
        else:
            cowork_results = [cowork_results]
    
    # 3. Merge & Deduplicate
    unified_findings = list(local_scores)
    unified_findings.extend(cowork_results)
    
    output_path = pair_dir / "unified_scores.json"
    output_path.write_text(json.dumps(unified_findings, indent=2), encoding="utf-8")
    
    # 4. Display Summary
    print("\n" + "="*80)
    print(f"📈 UNIFIED EVALUATION REPORT ({pair_dir.name})")
    print("="*80 + "\n")
    
    # Group by Agent
    agents = {}
    for f in unified_findings:
        agent = f.get("agent_name", "Unknown Agent")
        if agent not in agents:
            agents[agent] = []
        agents[agent].append(f)
        
    for agent, findings in agents.items():
        print(f"🤖 {agent.upper()}")
        print("-" * 40)
        
        # Sort so blockers show up first, then improvements, then passes
        def get_severity_rank(f):
            # Check Cowork format first
            sev = str(f.get("severity", "")).lower()
            if sev == "blocker": return 0
            if sev == "improvement": return 1
            
            # Check Deterministic format
            for err in f.get("error_details", []):
                if str(err.get("severity", "")).lower() == "blocker": return 0
                if str(err.get("severity", "")).lower() == "improvement": return 1
            
            # No issues (Pass)
            if f.get("score", 0) == f.get("max_score", 5): return 3
            return 2

        sorted_findings = sorted(findings, key=get_severity_rank)
        
        for f in sorted_findings:
            dim = f.get("dimension", getattr(f, "issue", "Evaluation"))
            score = f.get("score", "N/A")
            max_score = f.get("max_score", "N/A")
            method = f.get("method", "cowork")
            
            # Extract error codes safely regardless of schema differences
            error_codes = []
            if "error_codes" in f:
                error_codes = f["error_codes"]
            elif "error_code" in f:
                error_codes = [f["error_code"]]
                
            code_str = f"[{','.join(error_codes)}]" if error_codes else "[OK]"
            
            # Determine severity emoji from the severity field, not full text search
            sev_field = str(f.get("severity", "")).lower()
            emoji = "✅"
            if sev_field == "blocker":
                emoji = "🚨"
            elif sev_field == "improvement" or (score != max_score and score != "N/A"):
                emoji = "⚠️"
                
            print(f"  {emoji} {code_str} {dim}")
            print(f"     Score: {score}/{max_score} | Method: {method.upper()}")
            
            # Notes / Evidence mapping
            notes = f.get("notes") or f.get("evidence") or f.get("recommendation", "")
            if notes and str(notes).strip() and emoji != "✅":
                # truncate long notes for displaying
                if len(str(notes)) > 150:
                    notes = str(notes)[:147] + "..."
                print(f"     Detail: {notes}")
                
        print()

    print(f"💾 Unified results saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Cowork evaluation results.")
    parser.add_argument("pair_dir", help="Path to the eval_results pair directory (e.g., eval_results/test_overhaul/P1)")
    args = parser.parse_args()
    ingest_cowork_results(Path(args.pair_dir))
