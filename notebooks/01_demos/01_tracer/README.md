## Tracer Demo — Semantic Verification Engine (SVE)

Start with **00_runtime_evaluation_walkthrough.ipynb** to see the system in action: deterministic routing, tiered evaluators, and semantic answer validation under strict runtime constraints.

The remaining notebooks explain how this behavior is enabled, moving upstream through the data lifecycle in the system:

1. **01_tracer_generation_pipeline.ipynb** — synthetic question generation and grounding  
2. **02_medallion_data_validation.ipynb** — Bronze → Silver → Gold validation pipeline  
3. **03_context_feature_layer_foundation.ipynb** — lightweight feature enrichment (context layer)

Together, these stages shift complexity offline, allowing the runtime engine to remain fast, predictable, and LLM-light.