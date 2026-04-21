"""Title Optimizer Agent — rewrites historical role titles for ATS alignment."""

import json

from src.llm import call_llm_json
from src.models import PriorityMap, RoleTitleRewrite


SYSTEM_PROMPT = """\
You are a resume title optimization specialist. You will receive:
- The raw Job Description text.
- The Strategist's Priority Map (which bullets were selected per JD requirement).
- The candidate's master resume (to see original role titles and context).

Your task is to review each historical role in the master resume and decide \
whether its title should be rewritten to better align with the target JD, \
given the specific bullets the Strategist has selected for that role.

For each role:
1. Identify the original title exactly as it appears in the master resume.
2. Consider what bullets from that role were selected by the Strategist \
   and what story they tell.
3. Provide a rationale analyzing whether a title rewrite is warranted — \
   does the original title already capture the selected work, or would a \
   different title better reflect both the work AND the JD's language?
4. If a rewrite is warranted, provide the optimized title. If the original \
   title is already the best honest representation, keep it unchanged.
5. REMOVAL ACCOUNTING: If the optimized title drops any word or function \
   from the original title, you MUST explicitly state what was removed and \
   why. Do not silently drop terms. If you cannot justify a removal with \
   evidence from the selected bullets, keep the original term.

HONESTY CONSTRAINTS:
- SENIORITY PROTECTION (both directions):
  - You MUST NOT inflate seniority (e.g. "Coordinator" → "Director").
  - You MUST NOT deflate seniority (e.g. "CTO" → "Developer", "VP" → "Lead").
  - Founding credentials ("Founder", "Co-Founder", "Owner") are NEVER removed \
    or replaced. They may be supplemented (e.g. "Founder & Growth Lead" is \
    acceptable; "Growth Lead" alone — dropping "Founder" — is not).
- ROLE-SCOPED TITLING: The optimized title must reflect ONLY activities \
  documented in the master resume under THAT specific role. Do not import \
  vocabulary from the target JD to describe past roles. If the candidate's \
  past role involved teaching but the JD is for Training Manager, do not \
  relabel the teaching role as "Training Manager" unless training \
  was the specifically documented function.
- TITLE TRANSLATION scope: "Industry translation" means mapping equivalent \
  titles across markets (e.g. "Ward Sister" → "Charge Nurse", \
  "Accounts Manager" → "Controller"). It does NOT mean rewriting a title to \
  mirror the target JD. The optimized title must describe what the candidate \
  ACTUALLY DID, not what the target job is called.
- You MUST NOT fabricate responsibilities not supported by the selected bullets.
- The optimized title must be defensible in an interview.

Return a JSON array of objects:
[
  {
    "original_title": "Exact title from master resume",
    "rationale": "Step-by-step reasoning. Include REMOVAL ACCOUNTING if any term is dropped.",
    "optimized_title": "The rewritten title, or the original if no change needed"
  }
]
"""



def _format_priority_map(priority_map: PriorityMap) -> str:
    """Format the Strategist's priority map for the Title Optimizer prompt."""
    lines = []
    for e in priority_map.entries:
        lines.append(f"### {e.requirement} [{e.priority.value}]")
        lines.append(f"Rationale: {e.rationale}")
        if e.master_resume_bullets:
            for b in e.master_resume_bullets:
                lines.append(f"  - {b}")
        if e.combination_directive:
            lines.append(f"Combination: {e.combination_directive}")
        lines.append("")
    return "\n".join(lines)


def optimize_titles(
    jd_text: str,
    priority_map: PriorityMap,
    master_resume_text: str,
) -> list[RoleTitleRewrite]:
    """Optimize historical role titles for ATS alignment.

    Returns a list of RoleTitleRewrite objects, one per role in the master resume.
    """
    priority_map_text = _format_priority_map(priority_map)
    user_prompt = (
        f"## Raw Job Description\n{jd_text}\n\n"
        f"## Strategist Priority Map (selected bullets)\n{priority_map_text}\n\n"
        f"## Master Resume\n{master_resume_text}"
    )

    raw_json = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    items = json.loads(raw_json)

    return [
        RoleTitleRewrite(
            original_title=item.get("original_title", ""),
            rationale=item.get("rationale", ""),
            optimized_title=item.get("optimized_title", ""),
        )
        for item in items
    ]
