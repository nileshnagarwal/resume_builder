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

## 2. Implied Environmental Context (Anti-Hallucination)
**Hypothesis**: The Hallucination Checker gets lenient when a candidate demonstrates a skill (e.g., mentoring) that *could* apply to an environment the JD requests (e.g., startup incubators), causing the LLM to rubber-stamp the environment framing as "capable" rather than flagging it as a missing factual history claim.

**Experiment Details**:
- **Scenario**: JD demands "startup incubator" experience. Candidate has "mentored early stage founders" but no actual incubator context in their master resume.
- **Trigger**: The Builder injects "capable of mentoring founders in startup incubators" into the summary.
- **Criteria**: The Hallucination checker MUST flag the "startup incubator" phrase as a blocker-severity hallucination, regardless of the candidate's mentoring capability.

**Metrics to Track**:
- Does the phrase get passed as `[CLEAN]` or flagged as `[HALLUCINATION]`?
- Does the reasoning block correctly identify that the environment itself is missing?
