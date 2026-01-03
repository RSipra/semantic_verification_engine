# Prompt Engineering Experiments (Phase 2)

This directory contains prompt iteration artifacts and experimentation scripts
used to design the synthetic question generation strategy for the Content Factory.

These prompts were evaluated through:
- Manual API calls
- Batch experimentation via `experiments.yaml`
- Quality inspection in notebooks (see [link](../../../notebooks/02_research/03_aces_generating_new_questions/))

Outcomes of this work informed:
- ADR: Generative model selection
- ADR: Shift-left enrichment decision
- Dataset composition strategy


These files are not used at runtime or in production pipelines.
