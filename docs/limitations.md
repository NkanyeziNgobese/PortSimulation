# Limitations

This section documents current, evidence-based limitations of the project.

## Model coverage

- The CLI demo is a lightweight, synthetic run for reviewer convenience and is not a calibrated operational model.
- The CLI demo does not include the vessel/berth layer or TAS logic (those remain notebook-only).
- The "improved" scenario in the CLI demo is intentionally identical to baseline; improvements are planned but not wired.

## Behavior gaps

- Customs hold and rebooking logic are defined in helper functions but are not wired into the main container flow.
- Several KPI columns in the notebook depend on timestamps that are not always recorded (e.g., customs-related fields).

## Data and provenance

- Raw source files referenced by ingestion configs live under `$backup/` in this workspace and are not included in the repo.
- Vessel-layer parameters previously tied to a missing source file remain assumptions until sources are provided.
- The web export path uses notebook execution to generate JSON, which is brittle compared to a module API.

## Reproducibility and tests

- Deterministic seeding is implemented for the CLI demo only; notebook runs remain non-deterministic unless seeded manually.
- Automated tests are limited to a demo smoke test; there are no full-model regression tests.

## Performance

- Notebook runs can be heavy due to large CSV loads and full-horizon simulations.
