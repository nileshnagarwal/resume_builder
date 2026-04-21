"""Central configuration for the Resume Builder pipeline."""

import os
from pathlib import Path

# --- Project Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
MASTER_RESUME_DIR = PROJECT_ROOT / "master_resumes"
JD_DIR = PROJECT_ROOT / "jds"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHROMA_DB_DIR = PROJECT_ROOT / "data" / "chroma_db"
PROMPTS_DIR = PROJECT_ROOT  # Builder/Critique instruction files live at root

# --- LLM Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-3.1-flash-lite-preview"

# --- Pipeline Settings ---
MAX_REVISION_LOOPS = 3

# --- Prompt File Paths ---
BUILDER_PROMPT_PATH = PROMPTS_DIR / "Resume_Builder_Instructions_20260320.txt"
CRITIQUE_PROMPT_PATH = PROMPTS_DIR / "Resume_Critique_Instructions_20260320.txt"

# --- Resume Formatting Rules ---
SUMMARY_BULLET_RANGE = (3, 4)
MOST_RECENT_JOB_BULLET_RANGE = (5, 6)
PAST_JOB_BULLET_RANGE = (2, 3)

# --- Tone & Language ---
BANNED_HERO_WORDS = [
    "spearheaded", "drove transformation", "championed",
    "revolutionized", "orchestrated", "pioneered",
    "trailblazed", "masterminded",
    # Credential inflation — self-applied labels not backed by evidence
    "thought leader", "visionary", "innovative", "transformative",
    "world-class", "cutting-edge", "game-changing",
    "exceptional", "passionate", "dynamic",
]

PREFERRED_VERBS = [
    "handled", "reviewed", "tracked", "worked with",
    "set up", "guided", "managed", "built", "designed",
    "coordinated", "maintained", "prepared",
]
