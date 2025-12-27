#!/usr/bin/env python
"""
Dependencies
- Python 3.9+
- pandas
- openpyxl (for .xlsx)
- xlrd (for .xls)
- pyyaml (for config)
- pyarrow (optional, for parquet output)

Observed structure (sampled before coding)
- Files sampled:
  - unit volume january 2024.xlsx
  - unit volume august 2024.xls
  - unit volume April 2025.xlsx
- Each file had a single sheet named like: shipping_stats_YYYYMM
- Header row was the first row with columns:
  Date, Facility Code, Category, POL Unloc Country Code, POL, POD Unloc Country Code,
  POD, pod1, pol1, POD2, Dest, iso_code, Type Length, Freight Kind, Reefer Type, Reqs Power
- No explicit volume column was present; each row appears to represent one container unit

How to test (numbered steps)
1) Ensure Excel reports exist under the input folder in config_unit_volume.yml.
2) From repo root, run: python scripts/ingest/ingest_unit_volume_reports.py
3) Check data/processed/unit_volume for CSV/Parquet outputs and ingestion_log.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - import guard for runtime
    yaml = None


DEFAULT_CONFIG_PATH = Path("scripts/ingest/config_unit_volume.yml")


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("\n", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_config(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError(
            "pyyaml is required. Install with: python -m pip install pyyaml"
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_excel_files(input_dir: Path) -> List[Path]:
    patterns = ["*.xlsx", "*.xls", "*.xlsm"]
    files: List[Path] = []
    for pattern in patterns:
        files.extend(input_dir.glob(pattern))
    return sorted(files)


def excel_engine_for(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    return None


def build_synonym_lookup(column_mappings: dict) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for canonical, synonyms in column_mappings.items():
        names = [canonical] + list(synonyms or [])
        for name in names:
            key = normalize_text(name)
            if key:
                lookup[key] = canonical
    return lookup


def detect_header_row(
    preview: pd.DataFrame,
    synonym_lookup: Dict[str, str],
    min_match_count: int,
) -> Tuple[Optional[int], int, List[str]]:
    best_idx = None
    best_count = 0
    best_fields: List[str] = []
    for idx, row in preview.iterrows():
        values = [normalize_text(v) for v in row.tolist() if str(v).strip() != "nan"]
        matched = {synonym_lookup[v] for v in values if v in synonym_lookup}
        match_count = len(matched)
        if match_count > best_count:
            best_idx = idx
            best_count = match_count
            best_fields = sorted(matched)
    if best_count < min_match_count:
        return None, 0, []
    return best_idx, best_count, best_fields


def sheet_name_score(sheet_name: str, patterns: List[str]) -> int:
    name = sheet_name.lower()
    score = 0
    for pat in patterns:
        if pat.lower() in name:
            score += 1
    return score


def choose_sheet_and_header(
    xl: pd.ExcelFile,
    config: dict,
    synonym_lookup: Dict[str, str],
) -> Tuple[Optional[str], Optional[int], int, List[str], List[dict]]:
    sheet_patterns = config.get("sheet_name_patterns", [])
    max_scan_rows = int(config["header_detection"]["max_scan_rows"])
    min_match_count = int(config["header_detection"]["min_match_count"])

    candidates = xl.sheet_names
    best = (None, None, 0, [])
    sheet_logs: List[dict] = []

    for sheet in candidates:
        try:
            preview = xl.parse(sheet, header=None, nrows=max_scan_rows)
        except Exception as exc:
            sheet_logs.append(
                {
                    "sheet": sheet,
                    "status": "error",
                    "error": str(exc),
                }
            )
            continue

        header_idx, match_count, matched_fields = detect_header_row(
            preview, synonym_lookup, min_match_count
        )
        score = match_count + sheet_name_score(sheet, sheet_patterns)
        sheet_logs.append(
            {
                "sheet": sheet,
                "status": "scanned",
                "header_row": header_idx,
                "match_count": match_count,
                "matched_fields": matched_fields,
                "score": score,
            }
        )
        if header_idx is None:
            continue
        if score > best[2]:
            best = (sheet, header_idx, score, matched_fields)

    return best[0], best[1], best[2], best[3], sheet_logs


def parse_report_month(
    filename: str,
    sheet_names: List[str],
    config: dict,
) -> Optional[str]:
    patterns = config.get("filename_month_regexes", [])
    month_map = config.get("month_name_map", {})

    def _extract(text: str) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern["pattern"], text, re.IGNORECASE)
            if not match:
                continue
            year = match.groupdict().get("year")
            month_num = match.groupdict().get("month_num")
            month_name = match.groupdict().get("month_name")
            if year:
                year = int(year)
            if month_num:
                month = int(month_num)
            elif month_name:
                key = month_name.lower()
                month = month_map.get(key)
            else:
                month = None
            if year and month and 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
        return None

    report_month = _extract(filename)
    if report_month:
        return report_month

    for name in sheet_names:
        report_month = _extract(name)
        if report_month:
            return report_month

    return None


def normalize_category(value: object, category_map: dict) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NA
    text = str(value).strip().lower()
    if not text:
        return pd.NA
    return category_map.get(text, text.upper())


def clean_object_series(series: pd.Series) -> pd.Series:
    def _clean(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return pd.NA
        text = str(val).strip()
        if text in {"", "nan", "None"}:
            return pd.NA
        return text

    return series.map(_clean)


def standardize_dataframe(
    df: pd.DataFrame,
    config: dict,
    synonym_lookup: Dict[str, str],
    warnings: List[str],
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    column_mappings = config["column_mappings"]
    keep_unmapped = bool(config.get("options", {}).get("keep_unmapped_columns", False))

    col_map: Dict[str, str] = {}
    for col in df.columns:
        norm = normalize_text(col)
        if norm in synonym_lookup:
            canonical = synonym_lookup[norm]
            if canonical in col_map:
                warnings.append(
                    f"Duplicate mapping for {canonical}: {col_map[canonical]} and {col}"
                )
                continue
            col_map[canonical] = col

    df = df.rename(columns={orig: canon for canon, orig in col_map.items()})

    # Ensure all standard columns exist
    for canonical in column_mappings.keys():
        if canonical not in df.columns:
            df[canonical] = pd.NA

    # Optionally drop unmapped columns
    if not keep_unmapped:
        df = df[list(column_mappings.keys())]

    # Clean object columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = clean_object_series(df[col])

    # Drop empty rows in mapped columns
    df = df.dropna(how="all", subset=list(column_mappings.keys()))

    # Normalize date column
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Normalize category values
    category_map = config.get("category_value_map", {})
    if "category" in df.columns:
        df["category"] = df["category"].map(lambda v: normalize_category(v, category_map))

    return df, col_map


def infer_unit_from_volume_column(volume_col: Optional[str], config: dict) -> str:
    default_unit = config.get("unit_rules", {}).get("default_unit", "containers")
    if not volume_col:
        return default_unit
    volume_unit_map = config.get("unit_rules", {}).get("volume_column_units", {})
    norm = normalize_text(volume_col)
    for key, unit in volume_unit_map.items():
        if key.lower() in norm:
            return unit
    return default_unit


def finalize_dataset(
    df: pd.DataFrame,
    report_month: str,
    source_file: str,
    config: dict,
    warnings: List[str],
    volume_source_name: Optional[str],
) -> pd.DataFrame:
    # Volume and unit
    treat_missing_as_units = bool(
        config.get("options", {}).get("treat_missing_volume_as_units", True)
    )
    volume_col_present = "volume" in df.columns and df["volume"].notna().any()
    if volume_col_present:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        unit = infer_unit_from_volume_column(volume_source_name, config)
    else:
        if treat_missing_as_units:
            df["volume"] = 1
            unit = config.get("unit_rules", {}).get("default_unit", "containers")
            warnings.append("No volume column found; defaulted volume=1 per row.")
        else:
            df["volume"] = pd.NA
            unit = config.get("unit_rules", {}).get("default_unit", "containers")
    df["unit"] = unit

    # Terminal or pier derived
    if "terminal" in df.columns and df["terminal"].notna().any():
        df["terminal"] = df["terminal"].fillna(pd.NA)
    elif "facility_code" in df.columns:
        df["terminal"] = df["facility_code"]
    else:
        df["terminal"] = pd.NA

    df["report_month"] = report_month
    df["source_file"] = source_file

    return df


def ensure_output_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df[columns]


def write_data_dictionary(path: Path, columns: List[str]) -> None:
    column_descriptions = {
        "report_month": "Report month derived from filename (YYYY-MM).",
        "source_file": "Original Excel filename.",
        "date": "Date field from report.",
        "terminal": "Terminal or pier (derived from facility_code when present).",
        "facility_code": "Facility code from report (example: CTCT).",
        "category": "Movement category (IMPORT, EXPORT, TRANSSHIPMENT).",
        "unit": "Unit for volume (containers by default).",
        "volume": "Volume value; defaults to 1 per row if no volume column exists.",
        "pol_country_code": "Port of loading country code (UN/LOCODE).",
        "pol": "Port of loading code.",
        "pod_country_code": "Port of discharge country code (UN/LOCODE).",
        "pod": "Port of discharge code.",
        "pod1": "Additional POD field from report.",
        "pol1": "Additional POL field from report.",
        "pod2": "Secondary POD field from report.",
        "dest": "Destination field from report.",
        "iso_code": "ISO container type code.",
        "type_length": "Container length/type field from report.",
        "freight_kind": "Freight kind (example: MTY for empty).",
        "reefer_type": "Reefer type from report.",
        "reqs_power": "Requires power flag from report.",
    }

    lines = []
    lines.append("# Unit Volume Data Dictionary\n")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("\n## Columns\n")
    for col in columns:
        desc = column_descriptions.get(col, "No description available.")
        lines.append(f"- {col}: {desc}\n")
    lines.append("\n## Notes\n")
    lines.append(
        "- Each row represents one unit when no explicit volume column is present.\n"
    )
    lines.append(
        "- report_month is parsed from the filename using configured regex patterns.\n"
    )
    lines.append(
        "- terminal is derived from facility_code if a terminal field is not present.\n"
    )

    path.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest unit volume Excel reports into a unified dataset."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config YAML.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Override input directory from config.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory from config.",
    )

    args = parser.parse_args()

    if not args.config.exists():
        print(f"Config not found: {args.config}")
        return 2

    config = load_config(args.config)
    input_dir = args.input_dir or Path(config["input_dir"])
    output_dir = args.output_dir or Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list_excel_files(input_dir)
    if not files:
        print(f"No Excel files found in {input_dir}")
        return 1

    synonym_lookup = build_synonym_lookup(config["column_mappings"])
    log = {
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files_total": len(files),
        "files_processed": 0,
        "files_skipped": 0,
        "months_covered": [],
        "errors": [],
        "warnings": [],
        "file_logs": [],
    }

    combined: List[pd.DataFrame] = []
    months: List[str] = []

    for path in files:
        print(f"Processing: {path.name}")
        file_log = {
            "file": path.name,
            "path": str(path),
            "report_month": None,
            "selected_sheet": None,
            "header_row": None,
            "matched_fields": [],
            "status": "pending",
            "warnings": [],
            "error": None,
            "sheet_logs": [],
        }

        engine = excel_engine_for(path)
        try:
            xl = pd.ExcelFile(path, engine=engine)
        except Exception as exc:
            msg = f"Failed to open {path.name}: {exc}"
            print(f"  ERROR: {msg}")
            file_log["status"] = "error"
            file_log["error"] = msg
            log["errors"].append(msg)
            log["file_logs"].append(file_log)
            log["files_skipped"] += 1
            continue

        report_month = parse_report_month(path.name, xl.sheet_names, config)
        if not report_month:
            warning = "Could not parse report_month from filename or sheet name."
            file_log["warnings"].append(warning)
            log["warnings"].append(f"{path.name}: {warning}")

        sheet_name, header_row, score, matched_fields, sheet_logs = choose_sheet_and_header(
            xl, config, synonym_lookup
        )
        file_log["sheet_logs"] = sheet_logs
        if not sheet_name or header_row is None:
            msg = f"No suitable sheet/header found in {path.name}"
            print(f"  SKIP: {msg}")
            file_log["status"] = "skipped"
            file_log["error"] = msg
            log["errors"].append(msg)
            log["file_logs"].append(file_log)
            log["files_skipped"] += 1
            continue

        try:
            df_raw = xl.parse(sheet_name, header=header_row)
        except Exception as exc:
            msg = f"Failed to parse {path.name} sheet {sheet_name}: {exc}"
            print(f"  ERROR: {msg}")
            file_log["status"] = "error"
            file_log["error"] = msg
            log["errors"].append(msg)
            log["file_logs"].append(file_log)
            log["files_skipped"] += 1
            continue

        # Drop unnamed columns
        df_raw = df_raw.loc[:, ~df_raw.columns.astype(str).str.match(r"^Unnamed")]

        warnings: List[str] = []
        df_std, column_sources = standardize_dataframe(
            df_raw, config, synonym_lookup, warnings
        )
        volume_source_name = column_sources.get("volume")
        df_std = finalize_dataset(
            df_std,
            report_month or "unknown",
            path.name,
            config,
            warnings,
            volume_source_name,
        )

        # Basic confidence checks
        required_fields = config.get("required_fields", ["date", "category"])
        missing = [f for f in required_fields if f not in df_std.columns or df_std[f].isna().all()]
        if missing:
            warn = f"Missing required fields: {', '.join(missing)}"
            warnings.append(warn)

        file_log["report_month"] = report_month
        file_log["selected_sheet"] = sheet_name
        file_log["header_row"] = header_row
        file_log["matched_fields"] = matched_fields
        file_log["warnings"] = warnings
        file_log["status"] = "processed"

        log["files_processed"] += 1
        log["file_logs"].append(file_log)

        if report_month:
            months.append(report_month)

        combined.append(df_std)
        print(f"  Rows: {len(df_std)} | Sheet: {sheet_name} | Header row: {header_row}")
        if warnings:
            for warn in warnings:
                print(f"  WARN: {warn}")

    if not combined:
        print("No data processed. Exiting without outputs.")
        return 1

    df_all = pd.concat(combined, ignore_index=True)

    # Output columns (consistent schema)
    output_columns = [
        "report_month",
        "source_file",
        "date",
        "terminal",
        "facility_code",
        "category",
        "unit",
        "volume",
        "pol_country_code",
        "pol",
        "pod_country_code",
        "pod",
        "pod1",
        "pol1",
        "pod2",
        "dest",
        "iso_code",
        "type_length",
        "freight_kind",
        "reefer_type",
        "reqs_power",
    ]
    df_all = ensure_output_columns(df_all, output_columns)

    # Write outputs
    output_long = output_dir / config["output"]["long_filename"]
    df_all.to_csv(output_long, index=False)

    output_parquet = output_dir / config["output"]["parquet_filename"]
    try:
        df_all.to_parquet(output_parquet, index=False)
    except Exception as exc:
        msg = f"Parquet write skipped: {exc}"
        print(f"  WARN: {msg}")
        log["warnings"].append(msg)

    # Wide output if feasible
    wide_cfg = config.get("wide_output", {})
    if wide_cfg.get("enabled", True):
        group_by = wide_cfg.get("group_by", ["terminal", "category", "unit"])
        group_by = [c for c in group_by if c in df_all.columns and df_all[c].notna().any()]
        if "report_month" in df_all.columns and group_by:
            wide = (
                df_all.pivot_table(
                    index=group_by,
                    columns="report_month",
                    values=wide_cfg.get("value_column", "volume"),
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
            )
            output_wide = output_dir / config["output"]["wide_filename"]
            wide.to_csv(output_wide, index=False)
        else:
            msg = "Wide output skipped: missing report_month or group_by columns."
            print(f"  WARN: {msg}")
            log["warnings"].append(msg)

    # Data dictionary and log
    data_dict_path = output_dir / "data_dictionary.md"
    write_data_dictionary(data_dict_path, output_columns)

    log["months_covered"] = sorted(set(months))
    log["row_count"] = int(len(df_all))
    log_path = output_dir / "ingestion_log.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    # Summary
    print("\nSummary")
    print(f"- Files processed: {log['files_processed']} / {log['files_total']}")
    print(f"- Files skipped: {log['files_skipped']}")
    print(f"- Months covered: {', '.join(log['months_covered']) or 'none'}")
    print(f"- Total rows: {log['row_count']}")
    print(f"- Output folder: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
