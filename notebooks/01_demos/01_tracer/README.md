## Tracer Demo — Semantic Verification Engine (SVE)

Start with **00_runtime_evaluation_walkthrough.ipynb** to see the system in action: deterministic routing, tiered evaluators, and semantic answer validation under strict runtime constraints.

The remaining notebooks explain how this behavior is enabled, moving upstream through the data lifecycle in the system:

1. **01_tracer_generation_pipeline.ipynb** — synthetic question generation and grounding  
2. **02_medallion_data_validation.ipynb** — Bronze → Silver → Gold validation pipeline  
3. **03_context_feature_layer_foundation.ipynb** — lightweight feature enrichment (context layer)

Together, these stages shift complexity offline, allowing the runtime engine to remain fast, predictable, and LLM-light.

### Data and artifacts

The demo notebooks read from `data/02_intermediate/`, which holds outputs of the
**research** notebooks where this logic was developed — hence the `nbN_` naming,
which follows the research numbering, not the demo numbering. The demo chain is
not self-contained: nb02 starts from `dataframe_nb6_tracer_synthetic_v0` and nb03
from `dataframe_nb7-2_gold_tracer_v1`, both produced upstream in research.

The runtime artifact is `tracer_production_green_v1.parquet`. Notebook 03 writes
it to `data/02_intermediate/`; notebook 00 and the container read it from
`data/<nn>_final/`. The copy between them is **deliberately manual** — promoting
a dataset to `final/` is the point at which it is chosen for the container, so it
cannot happen as a side effect of re-running a notebook.

None of this uses the run-artifact scheme (manifest / calls / receipt /
quarantine) from `scripts/pipelines/`. The tracer predates those pipelines and
ran in notebooks, so its measurements are in the experiments yamls rather than
in run receipts.
