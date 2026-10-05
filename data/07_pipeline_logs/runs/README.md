# Run Artifacts

The prefeix of the run file indicates purpose:

- `run*`: real runs, kept as history. Receipts are never migrated, so readers
must tolerate fields that did not exist when an older receipt was written.

- `test*`: trial runs, written to `data/trial/` and not tracked.

Empty before the first book run. Everything prior was pipeline development:
single-chapter runs producing one to six questions, under naming conventions
that predate the current scheme.

The tracer predates this pipeline and ran in notebooks, so its artifacts are
elsewhere — intermediate outputs in `data/02_intermediate/`, the final
50-question dataset in `data/05_final/` (copied into the runtime container),
and the token and batch-size measurements in the experiments yamls.
