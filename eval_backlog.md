# Evaluation Backlog

This document tracks ideas and experiments to test once the automated evaluation framework (eval setup) is fully implemented.

## 1. Emotional and Reinforcement Prompting (A/B Testing)
**Hypothesis**: LLMs often take "lazy" shortcuts. By introducing emotional stimulus and explicit enforcement signals into system prompts, the models will engage in deeper reasoning and follow constraints more rigorously.

**Experiment Details**:
- **Control**: Current system prompts for `jd_extractor.py`, `fit_gatekeeper.py`, and `builder.py`.
- **Variant A (Positive Reinforcement)**: Add incentive phrases like *"I am going to tip you $200 for a perfect, well-reasoned solution!"*
- **Variant B (Negative Reinforcement)**: Add threat/penalty phrases like *"You will be severely penalized if you hallucinate facts or fail to strictly follow the formatting rules."*
- **Variant C (Combined)**: Use both positive incentives for quality and negative penalties for hallucinations.

**Metrics to Track**:
- Number of hallucinations or semantic drift cases.
- Constraint adherence (e.g., sticking to explicit bullet formatting).
- Quality score of the resulting step-by-step reasoning.
