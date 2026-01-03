# Pipeline Execution & Automation

This directory contains **production-ready scripts and pipelines** used to support
the Phase 2 Content Factory.

See the [Design Doc](../../docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) for pipeline architecture and decision context.

## Utility Scripts

Lightweight scripts used to automate one-off or infrequent tasks, such as:
- Downloading raw datasets (e.g. from Hugging Face)
- Extracting and formatting the Harry Potter corpus for source grounding in prompts

These scripts are not part of the runtime application and are executed manually or on demand.

## Content Factory Pipelines

This directory contains **hardened pipeline code** responsible for generating and validating
the trivia dataset in Phase 2.

- Pipelines are orchestrated using **Prefect**
- Inputs and outputs are **versioned datasets**
- Code here is intended to be deterministic and repeatable

Current pipelines:
- `generate_questions.py`

Exploratory logic, prompt experimentation, and analysis notebooks live under
`scripts/research/`.

