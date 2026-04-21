"""Data models for evaluation scores, agent traces, and eval reports."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Agent Trace — captures full I/O for a single agent invocation
# ---------------------------------------------------------------------------

def _safe_serialize(obj: Any) -> Any:
    """Convert an object to a JSON-serialisable form.

    Handles Pydantic models, dataclasses, enums, and arbitrary objects
    by falling back to str() so trace serialisation never crashes.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # Pydantic v1 / dataclass .dict()
    if hasattr(obj, "dict"):
        return obj.dict()
    # Enums
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


@dataclass
class AgentTrace:
    """Record of a single agent (or sub-agent) invocation."""
    agent_name: str
    loop_iteration: int       # 0 for initial pass, 1+ for revision loops
    state_before: dict        # full pipeline state snapshot before execution
    state_after: dict         # full pipeline state snapshot after execution
    elapsed_seconds: float
    timestamp: str = ""       # ISO 8601, set automatically if empty

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "loop_iteration": self.loop_iteration,
            "state_before": _safe_serialize(self.state_before),
            "state_after": _safe_serialize(self.state_after),
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Agent Score — a single scored dimension with optional error taxonomy tags
# ---------------------------------------------------------------------------

@dataclass
class AgentScore:
    agent_name: str
    dimension: str
    score: float
    max_score: float
    method: str  # "deterministic" or "llm_judge"
    notes: str = ""
    error_codes: list[str] = field(default_factory=list)
    error_details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "agent_name": self.agent_name,
            "dimension": self.dimension,
            "score": self.score,
            "max_score": self.max_score,
            "method": self.method,
            "notes": self.notes,
        }
        if self.error_codes:
            d["error_codes"] = self.error_codes
        if self.error_details:
            d["error_details"] = self.error_details
        return d


# ---------------------------------------------------------------------------
# Pair Result — full outcome for one eval pair
# ---------------------------------------------------------------------------

@dataclass
class PairResult:
    pair_id: str
    category: str
    success: bool
    elapsed_seconds: float
    error: Optional[str] = None
    fit_go: Optional[bool] = None
    fit_coverage: Optional[float] = None
    agent_scores: list[AgentScore] = field(default_factory=list)
    traces: list[AgentTrace] = field(default_factory=list)
    loops_to_ready: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "category": self.category,
            "success": self.success,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "error": self.error,
            "fit_go": self.fit_go,
            "fit_coverage": self.fit_coverage,
            "loops_to_ready": self.loops_to_ready,
            "agent_scores": [a.to_dict() for a in self.agent_scores],
            "trace_count": len(self.traces),
        }


# ---------------------------------------------------------------------------
# Eval Report — top-level container for a full eval run
# ---------------------------------------------------------------------------

@dataclass
class EvalReport:
    timestamp: str
    results: list[PairResult]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
        }
