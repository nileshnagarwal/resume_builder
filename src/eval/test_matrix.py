"""Evaluation Test Matrix encoding the Golden Dataset."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvalPair:
    pair_id: str
    category: str
    jd_file: str
    resume_file: str
    description: str
    expected_go: Optional[bool]
    expected_coverage_range: Optional[tuple[float, float]]


EVAL_MATRIX = [
    # Positive
    EvalPair("P1", "positive", "growth_partnerships_condovoter_260326.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "Trust evidence selection, anti-drift, tone", True, (65.0, 75.0)),
    EvalPair("P2", "positive", "business_development_manager_zymewire_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "Metrics vs narrative evidence choice", True, (50.0, 60.0)),
    EvalPair("P3", "positive", "director_operations_airia_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "Ops transfer across industries", True, (45.0, 55.0)),
    EvalPair("P4", "positive", "customer_success_tenor_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "Overqualification - must not inflate junior title", True, (55.0, 65.0)),
    EvalPair("P5", "positive", "business_development_manager_zymewire_260405.txt", "synthetic_metrics_dense.md", "Perfect match - metric JD + metric resume", True, (80.0, 90.0)),
    EvalPair("P6", "positive", "growth_partnerships_condovoter_260326.txt", "synthetic_metrics_dense.md", "Mismatch test - trust JD + metric resume", True, (50.0, 60.0)),
    
    # Negative
    EvalPair("N1", "negative", "ai_algorithm_engineer_supergeo_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "AI/ML JD vs ops profile - hard NO", False, (0.0, 20.0)),
    EvalPair("N2", "negative", "operations_engineer_saltworks_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "ChemE JD vs ops profile - hard NO", False, (0.0, 20.0)),
    EvalPair("N3", "negative", "director_consulting_salesforce_260405.txt", "Nilesh_Agarwal_Master_Resume_20260323.md", "Salesforce Director - missing core domain", False, (20.0, 40.0)),
    EvalPair("N4", "negative", "business_development_manager_zymewire_260405.txt", "synthetic_sparse.md", "SaaS BD vs sparse profile", False, (0.0, 15.0)),
    EvalPair("N5", "negative", "ai_algorithm_engineer_supergeo_260405.txt", "synthetic_functional_gap.md", "AI/ML JD vs functional gap resume", False, (0.0, 15.0)),

    # Boundary
    EvalPair("B1", "boundary", "business_development_manager_zymewire_260405.txt", "synthetic_borderline_fit.md", "BD JD + borderline profile", None, (45.0, 55.0)),
    EvalPair("B2", "boundary", "customer_success_tenor_260405.txt", "synthetic_borderline_fit.md", "Startup CS + borderline profile", None, (45.0, 55.0)),

    # Anti-Hallucination
    EvalPair("H1", "anti_hallucination", "growth_partnerships_condovoter_260326.txt", "synthetic_sparse.md", "Sparse resume + real JD", None, None),
    EvalPair("H2", "anti_hallucination", "director_operations_airia_260405.txt", "synthetic_sparse.md", "Manufacturing JD + sparse resume", None, None),

    # Format Robustness
    EvalPair("F1", "format_robustness", "growth_partnerships_condovoter_260326.txt", "synthetic_functional_gap.md", "Trust JD + functional format + 4-year gap", None, None),
    EvalPair("F2", "format_robustness", "director_operations_airia_260405.txt", "synthetic_functional_gap.md", "Ops JD + functional format", None, None),
]


def get_pairs(category: Optional[str] = None) -> list[EvalPair]:
    """Get eval pairs, optionally filtered by category."""
    if not category or category.lower() == "all":
        return EVAL_MATRIX
    return [p for p in EVAL_MATRIX if p.category == category.lower()]


def get_pair_by_id(pair_id: str) -> EvalPair:
    """Get a specific eval pair by ID."""
    for p in EVAL_MATRIX:
        if p.pair_id.upper() == pair_id.upper():
            return p
    raise ValueError(f"No eval pair found with ID {pair_id}")
