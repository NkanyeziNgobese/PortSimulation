# Unit Volume Data Dictionary
Generated: 2025-12-27 13:14:43

## Columns
- report_month: Report month derived from filename (YYYY-MM).
- source_file: Original Excel filename.
- date: Date field from report.
- terminal: Terminal or pier (derived from facility_code when present).
- facility_code: Facility code from report (example: CTCT).
- category: Movement category (IMPORT, EXPORT, TRANSSHIPMENT).
- unit: Unit for volume (containers by default).
- volume: Volume value; defaults to 1 per row if no volume column exists.
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

## Notes
- Each row represents one unit when no explicit volume column is present.
- report_month is parsed from the filename using configured regex patterns.
- terminal is derived from facility_code if a terminal field is not present.
