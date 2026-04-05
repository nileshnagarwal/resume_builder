"""CLI entry point for the Resume Builder pipeline."""

import argparse
import sys
import time
from pathlib import Path

from src.config import OUTPUT_DIR
from src.graph import build_pipeline
from src.vector_db import ingest_master_resume, load_master_resume


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume Builder — Multi-Agent Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m src.cli --jd jds/growth_partnerships_condovoter_260326.txt
  python -m src.cli --jd jds/my_job.txt --reingest
        """,
    )
    parser.add_argument(
        "--jd",
        required=True,
        type=Path,
        help="Path to the job description text file",
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Re-ingest the master resume into the vector DB before running",
    )

    args = parser.parse_args()

    # Validate JD file exists
    if not args.jd.exists():
        print(f"❌ JD file not found: {args.jd}")
        sys.exit(1)

    # Read JD
    jd_text = args.jd.read_text(encoding="utf-8")
    print(f"📄 Loaded JD: {args.jd.name} ({len(jd_text)} chars)")

    # Re-ingest master resume if requested
    if args.reingest:
        print("🔄 Re-ingesting master resume into vector DB...")
        count = ingest_master_resume()
        print(f"   Ingested {count} chunks")

    # Load master resume text
    master_resume_text = load_master_resume()
    print(f"📋 Loaded master resume ({len(master_resume_text)} chars)")

    # Build and run pipeline
    print("\n" + "=" * 60)
    print("  RESUME BUILDER PIPELINE")
    print("=" * 60)

    pipeline = build_pipeline()
    start_time = time.time()

    initial_state = {
        "jd_text": jd_text,
        "master_resume_text": master_resume_text,
        "requirements": [],
        "fit_result": None,
        "priority_map": None,
        "current_draft": None,
        "critique_flags": [],
        "critique_verdict": None,
        "diff_log": [],
        "loop_count": 0,
        "final_resume_md": "",
    }

    final_state = pipeline.invoke(initial_state)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"  ✅ PIPELINE COMPLETE in {elapsed:.1f}s")
    print(f"  📄 Output: {OUTPUT_DIR / 'tailored_resume.md'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
