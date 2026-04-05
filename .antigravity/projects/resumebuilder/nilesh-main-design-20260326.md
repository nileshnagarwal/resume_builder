# Design Doc: Two-Sided AI Resume & Matching Engine

## 1. The Premise
The current job application process forces high-resolution individuals and high-resolution job requirements through a low-resolution filter (the 1-page PDF resume). This results in massive friction, low conversion rates, and wasted time for both candidates and recruiters. 

## 2. The Wedge
Start as a single-player tool for the candidate. Automate the manual 1-2 hour process of tailoring a resume to a specific JD. 
- Deep integration of a Builder and Critique agent loop.
- Systematic Diff Logs to isolate feedback.
- Strict adherence to Tone & Language guidelines and a "Confirmed Gaps" ledger.

## 3. The Moat & The Master Profile
By using the tool, the candidate iteratively builds a "Master Profile"—a high-resolution, uncompressed database of their entire professional history, including nuances, failures, and granular STAR metrics that don't fit on a standard resume.

*Note on Data Lock-in:* The moat is the intelligence of the matching, not holding the user's data hostage. Allowing export builds trust; locking it down breeds resentment. 

## 4. Architecture (Multi-Agent System)
- **Data Layer:** Vector database representing the Master Profile (chunked STAR bullets, roles, skills).
- **Builder Agent:** Takes a JD, extracts requirements, queries the Vector DB for the best matching evidence, drafts V1.
- **Critique Agent:** Reviews V1 against strict rules (No hallucinations, correct bullet counts, Tone & Language checks). 
- **Diff Engine:** Builder processes critique, generates a structured diff log, drafts V2.
- **Memory/Updater Agent:** If the Builder needs missing context, it asks the user. The user's answer is permanently embedded back into the Master Profile.
