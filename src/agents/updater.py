"""Updater Agent — prompts user for missing info and updates the master resume."""

from src.vector_db import add_entry


def prompt_for_missing_context(
    unmatched_requirements: list[str],
) -> dict[str, str]:
    """Prompt the user via CLI for missing context on unmatched requirements.

    Returns a dict mapping requirement names to user-provided context.
    Only asks for requirements the user can actually address.
    """
    if not unmatched_requirements:
        return {}

    print("\n" + "=" * 60)
    print("UPDATER AGENT: Missing Context Detected")
    print("=" * 60)
    print(
        "\nThe following JD requirements have no match in your master resume."
        "\nFor each, please provide relevant experience or type 'skip' to skip.\n"
    )

    updates: dict[str, str] = {}
    for req in unmatched_requirements:
        print(f"\n📋 Requirement: {req}")
        response = input("   Your experience (or 'skip'): ").strip()
        if response.lower() != "skip" and response:
            updates[req] = response

    return updates


def update_master_resume(updates: dict[str, str]) -> int:
    """Write user-provided context into the vector DB.

    Returns the number of entries added.
    """
    count = 0
    for requirement, context in updates.items():
        text = f"[User-confirmed context for: {requirement}]\n{context}"
        add_entry(
            text=text,
            metadata={
                "source": "user_update",
                "requirement": requirement,
            },
        )
        count += 1
    return count
