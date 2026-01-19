# Prompt Library

This directory contains versioned prompt definitions used by the Content Factory pipelines.

Each prompt is treated as a first-class, versioned artifact. Prompt identifiers are recorded
in generated dataset rows to preserve provenance and support debugging and iteration.

## Prompt conventions

- Each prompt file defines a unique `prompt_id`
- Prompt files are versioned via Git
- Pipelines record `prompt_id` and `generation_run_id` per generated question

## Active prompts

### EX questions
- `ex_questions_v1.yaml` – Initial explanatory question generation
- `ex_questions_v2.yaml` – Refined prompt with tighter answer constraints

### FR questions
- `fr_questions_v1.yaml` – Short factual recall questions

## Notes

Prompt experimentation and evaluation are performed in notebooks under
`scripts/research/`. Once stabilized, prompts are promoted here for use in pipelines.