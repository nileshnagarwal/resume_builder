"""CLI entry point for the Eval Harness."""

import argparse
from pathlib import Path
from src.eval.runner import run_eval

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume Builder Eval Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--category", type=str, help="Filter by category (e.g. positive, negative, boundary)")
    parser.add_argument("--pairs", type=str, nargs="+", help="Run specific pair IDs (e.g. --pairs P1 N1)")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without saving artifacts or scoring")
    parser.add_argument("--no-score", action="store_true", help="Skip deterministic scorers")
    parser.add_argument("--output-dir", type=Path, help="Specific output directory")
    
    args = parser.parse_args()
    
    run_eval(
        category=args.category,
        pair_ids=args.pairs,
        dry_run=args.dry_run,
        score=not args.no_score,
        output_dir=args.output_dir
    )

if __name__ == "__main__":
    main()
