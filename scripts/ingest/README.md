# Unit Volume Ingestion Pipeline

## What this script does
- Reads all monthly unit volume Excel reports in the input folder.
- Detects the correct sheet and header row automatically.
- Normalizes columns into a consistent schema.
- Adds report_month and source_file.
- Outputs a unified long dataset, optional wide dataset, parquet, a data dictionary, and a JSON ingestion log.

## How to run
From repo root:
```bash
python scripts/ingest/ingest_unit_volume_reports.py
```

Optional overrides:
```bash
python scripts/ingest/ingest_unit_volume_reports.py --input-dir path/to/reports --output-dir data/processed/unit_volume
```

## Outputs
Written to the folder configured in `config_unit_volume.yml`:
- data/processed/unit_volume/unit_volume_long.csv
- data/processed/unit_volume/unit_volume_wide.csv (if feasible)
- data/processed/unit_volume/unit_volume.parquet
- data/processed/unit_volume/data_dictionary.md
- data/processed/unit_volume/ingestion_log.json

## Troubleshooting
- Missing openpyxl or xlrd:
  - Install with: `python -m pip install openpyxl xlrd`
- Missing pyyaml:
  - Install with: `python -m pip install pyyaml`
- Parquet write fails:
  - Install pyarrow: `python -m pip install pyarrow`
- Files are skipped:
  - Check `ingestion_log.json` for the specific error or warning.
  - Inspect sheet names and update `sheet_name_patterns` in the config.
  - Update `column_mappings` if headers are renamed.

## How to extend for other datasets
1) Copy `config_unit_volume.yml` and adjust:
   - input_dir and output_dir
   - sheet_name_patterns
   - column_mappings and required_fields
   - filename_month_regexes if month parsing differs
2) Reuse the same script and point to the new config with `--config`.

## Next steps
1) Add TEU derivation rules (for example from type_length or iso_code).
2) Add multiple run support and summary KPIs by month.
3) Add automated validation checks (row counts, null rates, and category distributions).
