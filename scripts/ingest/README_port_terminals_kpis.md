# Port Terminals KPI Ingestion

## What this script does
- Scans annual PDF reports for 2020-2025.
- Locates the section titled **"Overview of key performance indicators"**.
- Extracts KPI table rows (including multi-page tables).
- Normalizes the output into a tidy, analysis-ready dataset.
- Writes CSV + Parquet outputs and an ingestion log.

## How it finds the KPI section
1) Scans pages for the header line **"Key performance area and indicator"**.
2) Ignores table-of-contents pages.
3) Starts parsing from the first page containing the header.
4) Extracts rows until the next major section (e.g., "Financial performance review").

## Dependencies
Install required packages:
```bash
python -m pip install pdfplumber pandas
```
Optional for Parquet:
```bash
python -m pip install pyarrow
```
Optional fallback (if pdf text extraction is weak):
```bash
python -m pip install camelot-py
```

## How to run
From repo root:
```bash
python scripts/ingest/ingest_port_terminals_kpis.py
```

Outputs are written to:
```
data/processed/port_terminals_kpis/
```

## Output schema (long format)
Each row represents one KPI line with period values.
- report_year (int)
- kpi_section
- kpi_name
- terminal_or_scope
- submetric
- unit
- period_left_label / period_left_value
- period_mid_label / period_mid_value
- period_right_label / period_right_value
- period_next_label / period_next_value
- period_extra_labels / period_extra_values (JSON arrays if there are more than 4 periods)
- source_pdf
- source_page_start / source_page_end
- extraction_confidence (0-1)

## Troubleshooting (PDF extraction)
- **No rows extracted**:
  - Check that the PDF contains the expected heading.
  - Inspect `ingestion_log.json` for page ranges and warnings.
- **Wrong file names**:
  - The script first looks for `Port Terminals <year>.pdf`.
  - If missing, it falls back to any PDF containing "Port Terminals".
- **Misaligned values**:
  - Some PDFs have text extraction artifacts (merged words or lost spacing).
  - These rows still load, but may need manual cleanup downstream.
- **Parquet write fails**:
  - Install pyarrow or skip parquet output.

