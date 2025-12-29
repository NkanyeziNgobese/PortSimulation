# Unit Volume Data Dictionary
Generated: 2025-12-29 10:36:07

## Columns
- report_month: Report month inferred from date_raw or filename (YYYY-MM).
- source_file: Original Excel filename.
- report_period_start: Month start date (YYYY-MM-01).
- report_period_end: Month end date (YYYY-MM-DD).
- date_raw: Original Date column value from Excel (often a month label).
- facility_code: Facility code from report (example: CTCT).
- category: Movement category (IMPORT, EXPORT, TRANSSHIPMENT).
- pol_country_code: Port of loading country code (UN/LOCODE).
- pol: Port of loading code.
- pod_country_code: Port of discharge country code (UN/LOCODE).
- pod: Port of discharge code.
- pod1: Additional POD field from report.
- pol1: Additional POL field from report.
- pod2: Secondary POD field from report.
- dest: Destination field from report.
- iso_code: ISO container type code.
- type_length: Container length/type field from report.
- freight_kind: Freight kind (example: MTY for empty).
- reefer_type: Reefer type from report.
- reqs_power: Requires power flag from report.
- unit: Unit for volume (containers by default).
- volume: Volume value; defaults to 1 per row if no volume column exists.

## Notes
- Each row represents one unit when no explicit volume column is present.
- report_month is inferred from date_raw when available to avoid filename drift.
