# Data Usage and Provenance Notes

This repo includes processed datasets and benchmark notes. Raw source reports live under `$backup/` in this workspace and are not part of the repo.

## Included data

- `data/processed/unit_volume/*` (processed unit volume outputs + ingestion logs).
- `data/processed/port_terminals_kpis/*` (extracted KPI tables + ingestion logs).
- `data/benchmarks/port_efficiency_benchmarks.md` (benchmark ranges).

## Expected raw inputs (not committed)

| Ingestion config | Expected path | Actual path in this workspace |
| --- | --- | --- |
| `scripts/ingest/config_unit_volume.yml` | `data/reports/unit_volume_reports/` | `$backup/data_reports/unit_volume_reports/` |
| `scripts/ingest/ingest_port_terminals_kpis.py` | `data/reports/annual_results/<year>/annual/` | `$backup/data_reports/annual_results/<year>/annual/` |

## Licensing and provenance caution

- The raw reports under `$backup/` may have licensing restrictions. Do not redistribute them unless you have explicit permission.
- If you move or copy raw reports into `data/reports/`, update the ingestion configs and document the source.
