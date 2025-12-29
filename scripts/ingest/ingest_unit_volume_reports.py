#!/usr/bin/env python
"""
Dependencies
- Python 3.9+
- pandas
- openpyxl (for .xlsx)
- xlrd (for .xls)
- pyyaml (optional, for config)

Notes
- Excel "Date" often stores a month label (e.g., Feb-25), so we keep it as date_raw.
- report_month is inferred from date_raw first, then the filename if needed.
- When no numeric volume column exists, each row is treated as one unit (volume=1).

Usage
python scripts/ingest/ingest_unit_volume_reports.py --input_dir data/unit_volume_reports --output data/processed/unit_volume_ingested.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - import guard for runtime
    yaml = None


DEFAULT_CONFIG_PATH = Path("scripts/ingest/config_unit_volume.yml")
DEFAULT_INPUT_DIR = Path("data/unit_volume_reports")
DEFAULT_OUTPUT_PATH = Path("data/processed/unit_volume_ingested.csv")

CANONICAL_COLUMNS = [
    "report_month",
    "source_file",
    "report_period_start",
    "report_period_end",
    "date_raw",
    "facility_code",
    "category",
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
    "unit",
    "volume",
]

CRITICAL_COLUMNS = ["facility_code", "category", "pol", "pod"]

DEFAULT_HEADER_TOKENS = [
    "facility",
    "facility code",
    "category",
    "pol",
    "pod",
    "type length",
]

DEFAULT_COLUMN_SYNONYMS: Dict[str, List[str]] = {
    "date_raw": ["date", "report date", "reporting period", "month", "period"],
    "facility_code": ["facility code", "facility", "facilitycode", "facility_code"],
    "category": ["category", "move type", "move", "direction"],
    "pol_country_code": [
        "pol unloc country code",
        "pol country code",
        "pol country",
        "pol_unloc_country_code",
    ],
    "pol": ["pol", "port of loading"],
    "pod_country_code": [
        "pod unloc country code",
        "pod country code",
        "pod country",
        "pod_unloc_country_code",
    ],
    "pod": ["pod", "port of discharge"],
    "pod1": ["pod1"],
    "pol1": ["pol1"],
    "pod2": ["pod2"],
    "dest": ["dest", "destination"],
    "iso_code": ["iso_code", "iso code", "iso"],
    "type_length": ["type length", "type_length", "length", "size", "container size"],
    "freight_kind": ["freight kind", "freight_kind"],
    "reefer_type": ["reefer type", "reefer_type"],
    "reqs_power": ["reqs power", "requires power", "power reqs", "req power"],
    "volume": ["volume", "teu", "teus", "units", "count"],
}

DEFAULT_CATEGORY_VALUE_MAP = {
    "import": "IMPORT",
    "imports": "IMPORT",
    "exp": "EXPORT",
    "export": "EXPORT",
    "exports": "EXPORT",
    "trans": "TRANSSHIPMENT",
    "transhipment": "TRANSSHIPMENT",
    "transshipment": "TRANSSHIPMENT",
}

DEFAULT_MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

DEFAULT_FILENAME_MONTH_REGEXES = [
    {
        "pattern": (
            r"(?P<month_name>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
            r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
            r"dec(?:ember)?)\\s*(?P<year>20\\d{2})"
        )
    },
    {"pattern": r"(?P<year>20\\d{2})[^0-9]?(?P<month_num>0?[1-9]|1[0-2])"},
    {"pattern": r"(?P<year>20\\d{2})(?P<month_num>0[1-9]|1[0-2])"},
]

DEFAULT_HEADER_DETECTION = {"max_scan_rows": 30, "min_match_count": 3}

NULL_LIKE = {"", "null", "nan", "none"}


def normalize_header(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("\n", " ").replace("\t", " ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError(
            "pyyaml is required. Install with: python -m pip install pyyaml"
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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


def build_column_synonyms(config: Optional[dict]) -> Dict[str, List[str]]:
    config = config or {}
    synonyms: Dict[str, List[str]] = {}
    for canon in CANONICAL_COLUMNS:
        synonyms[canon] = list(DEFAULT_COLUMN_SYNONYMS.get(canon, []))

    for key, values in (config.get("column_mappings") or {}).items():
        canonical = "date_raw" if key == "date" else key
        if canonical not in synonyms:
            continue
        for value in values or []:
            synonyms[canonical].append(value)

    return synonyms


def build_synonym_lookup(column_synonyms: Dict[str, List[str]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for canonical, synonyms in column_synonyms.items():
        names = [canonical] + list(synonyms or [])
        for name in names:
            key = normalize_header(name)
            if key:
                lookup[key] = canonical
    return lookup


def find_header_row(
    preview: pd.DataFrame,
    header_tokens: List[str],
    min_match_count: int,
) -> Tuple[Optional[int], int, List[str]]:
    # We scan early rows to avoid title blocks and find the actual header row.
    tokens = {normalize_header(token) for token in header_tokens}
    for idx, row in preview.iterrows():
        values = [
            normalize_header(v) for v in row.tolist() if not pd.isna(v) and str(v).strip()
        ]
        matched = {v for v in values if v in tokens}
        if len(matched) >= min_match_count:
            return idx, len(matched), sorted(matched)
    return None, 0, []


def normalize_columns(
    df: pd.DataFrame,
    column_synonyms: Dict[str, List[str]],
    warnings: List[str],
    keep_unmapped: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    normalized = {col: normalize_header(col) for col in df.columns}
    df = df.rename(columns=normalized)

    lookup = build_synonym_lookup(column_synonyms)
    col_map: Dict[str, str] = {}
    for col in df.columns:
        canonical = lookup.get(col)
        if not canonical:
            continue
        if canonical in col_map:
            warnings.append(
                f"Duplicate mapping for {canonical}: {col_map[canonical]} and {col}"
            )
            continue
        col_map[canonical] = col

    df = df.rename(columns={src: dest for dest, src in col_map.items()})

    for canonical in CANONICAL_COLUMNS:
        if canonical not in df.columns:
            df[canonical] = pd.NA

    if keep_unmapped:
        extras = [col for col in df.columns if col not in CANONICAL_COLUMNS]
        df = df[CANONICAL_COLUMNS + extras]
    else:
        df = df[CANONICAL_COLUMNS]

    return df, col_map


def clean_object_series(series: pd.Series) -> pd.Series:
    def _clean(val: object) -> object:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return pd.NA
        text = str(val).strip()
        if not text:
            return pd.NA
        if text.lower() in NULL_LIKE:
            return pd.NA
        return text

    return series.map(_clean)


def normalize_category(series: pd.Series, category_map: Dict[str, str]) -> pd.Series:
    def _norm(val: object) -> object:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return pd.NA
        text = str(val).strip()
        if not text or text.lower() in NULL_LIKE:
            return pd.NA
        text_lower = text.lower()
        return category_map.get(text_lower, text.upper())

    return series.map(_norm)


def parse_type_length(val: object) -> object:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return pd.NA
    if isinstance(val, (int, float)) and not pd.isna(val):
        return int(val)
    text = str(val)
    match = re.search(r"\\d+", text)
    if match:
        return int(match.group())
    return pd.NA


def parse_month_from_text(value: object, month_name_map: Dict[str, int]) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return f"{value.year:04d}-{value.month:02d}"
    text = str(value).strip()
    if not text or text.lower() in NULL_LIKE:
        return None

    match = re.search(
        r"(?P<month_name>[A-Za-z]{3,9})[^0-9]*(?P<year>\\d{2,4})",
        text,
    )
    if match:
        month_name = match.group("month_name").lower()
        month = month_name_map.get(month_name)
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        if month:
            return f"{year:04d}-{month:02d}"

    match = re.search(r"(?P<year>20\\d{2})[^0-9]*(?P<month_num>0?[1-9]|1[0-2])", text)
    if match:
        year = int(match.group("year"))
        month = int(match.group("month_num"))
        return f"{year:04d}-{month:02d}"

    match = re.search(r"(?P<month_num>0?[1-9]|1[0-2])[^0-9]*(?P<year>20\\d{2})", text)
    if match:
        year = int(match.group("year"))
        month = int(match.group("month_num"))
        return f"{year:04d}-{month:02d}"

    return None


def parse_report_month_from_patterns(
    text: str,
    patterns: List[dict],
    month_name_map: Dict[str, int],
) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern["pattern"], text, re.IGNORECASE)
        if not match:
            continue
        year = match.groupdict().get("year")
        month_num = match.groupdict().get("month_num")
        month_name = match.groupdict().get("month_name")
        year_value = int(year) if year else None
        if month_num:
            month_value = int(month_num)
        elif month_name:
            month_value = month_name_map.get(month_name.lower())
        else:
            month_value = None
        if year_value and month_value and 1 <= month_value <= 12:
            return f"{year_value:04d}-{month_value:02d}"
    return None


def infer_report_month(
    file_path: Path,
    df: pd.DataFrame,
    config: Optional[dict] = None,
) -> Tuple[Optional[str], str]:
    # Prefer month inference from the Excel date column to avoid guesswork from filenames.
    config = config or {}
    month_name_map = config.get("month_name_map", DEFAULT_MONTH_NAME_MAP)
    date_values = df["date_raw"] if "date_raw" in df.columns else pd.Series([], dtype=object)
    months: List[str] = []
    for val in date_values:
        month = parse_month_from_text(val, month_name_map)
        if month:
            months.append(month)
    if months:
        report_month = pd.Series(months).mode().iloc[0]
        return report_month, "date_raw"

    filename = file_path.stem
    report_month = parse_month_from_text(filename, month_name_map)
    if report_month:
        return report_month, "filename"

    patterns = config.get("filename_month_regexes", DEFAULT_FILENAME_MONTH_REGEXES)
    report_month = parse_report_month_from_patterns(filename, patterns, month_name_map)
    if report_month:
        return report_month, "filename"

    return None, "unknown"


def build_report_periods(report_month: Optional[str]) -> Tuple[object, object]:
    if not report_month:
        return pd.NA, pd.NA
    start = pd.to_datetime(f"{report_month}-01", errors="coerce")
    if pd.isna(start):
        return pd.NA, pd.NA
    start_date = start.date().isoformat()
    end_date = (start + pd.offsets.MonthEnd(0)).date().isoformat()
    return start_date, end_date


def infer_unit_from_volume_column(volume_col: Optional[str], config: dict) -> str:
    default_unit = config.get("unit_rules", {}).get("default_unit", "containers")
    if not volume_col:
        return default_unit
    volume_unit_map = config.get("unit_rules", {}).get("volume_column_units", {})
    norm = normalize_header(volume_col)
    for key, unit in volume_unit_map.items():
        if key.lower() in norm:
            return unit
    return default_unit


def apply_volume_and_unit(
    df: pd.DataFrame,
    volume_source_name: Optional[str],
    config: dict,
    warnings: List[str],
) -> None:
    # If no numeric volume exists, treat each row as one unit to keep counts correct.
    default_unit = config.get("unit_rules", {}).get("default_unit", "containers")
    if "volume" in df.columns:
        numeric = pd.to_numeric(df["volume"], errors="coerce")
        if numeric.notna().any():
            df["volume"] = numeric
            df["unit"] = infer_unit_from_volume_column(volume_source_name, config)
            return

    df["volume"] = 1
    df["unit"] = default_unit
    warnings.append("No numeric volume column found; defaulted volume=1 per row.")


def ingest_one_excel(
    path: Path,
    config: dict,
    column_synonyms: Dict[str, List[str]],
    header_tokens: List[str],
) -> Tuple[Optional[pd.DataFrame], dict]:
    file_log = {
        "file": path.name,
        "path": str(path),
        "report_month": None,
        "report_month_source": None,
        "report_period_start": None,
        "report_period_end": None,
        "rows": 0,
        "unique_facility_codes": 0,
        "missing_critical_columns": [],
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
        file_log["status"] = "error"
        file_log["error"] = f"Failed to open: {exc}"
        return None, file_log

    header_cfg = config.get("header_detection", DEFAULT_HEADER_DETECTION)
    max_scan_rows = int(header_cfg.get("max_scan_rows", DEFAULT_HEADER_DETECTION["max_scan_rows"]))
    min_match_count = int(header_cfg.get("min_match_count", DEFAULT_HEADER_DETECTION["min_match_count"]))

    selected_sheet = None
    header_row = None
    matched_fields: List[str] = []

    for sheet in xl.sheet_names:
        try:
            preview = xl.parse(sheet, header=None, nrows=max_scan_rows)
        except Exception as exc:
            file_log["sheet_logs"].append(
                {"sheet": sheet, "status": "error", "error": str(exc)}
            )
            continue
        row_idx, match_count, matched_tokens = find_header_row(
            preview, header_tokens, min_match_count
        )
        file_log["sheet_logs"].append(
            {
                "sheet": sheet,
                "status": "scanned",
                "header_row": row_idx,
                "match_count": match_count,
                "matched_fields": matched_tokens,
            }
        )
        if row_idx is not None:
            selected_sheet = sheet
            header_row = row_idx
            matched_fields = matched_tokens
            break

    if selected_sheet is None and xl.sheet_names:
        # Fall back to the first sheet if detection fails, but flag it for review.
        selected_sheet = xl.sheet_names[0]
        header_row = 0
        file_log["warnings"].append("Header tokens not found; defaulted to first row.")

    if selected_sheet is None or header_row is None:
        file_log["status"] = "skipped"
        file_log["error"] = "No suitable sheet/header found."
        return None, file_log

    try:
        df_raw = xl.parse(selected_sheet, header=header_row)
    except Exception as exc:
        file_log["status"] = "error"
        file_log["error"] = f"Failed to parse sheet {selected_sheet}: {exc}"
        return None, file_log

    df_raw = df_raw.loc[:, ~df_raw.columns.astype(str).str.match(r"^Unnamed")]

    warnings: List[str] = []
    keep_unmapped = bool(config.get("options", {}).get("keep_unmapped_columns", False))
    df, column_sources = normalize_columns(
        df_raw, column_synonyms, warnings, keep_unmapped=keep_unmapped
    )

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = clean_object_series(df[col])

    category_map = config.get("category_value_map", DEFAULT_CATEGORY_VALUE_MAP)
    if "category" in df.columns:
        df["category"] = normalize_category(df["category"], category_map)

    if "type_length" in df.columns:
        df["type_length"] = df["type_length"].map(parse_type_length)

    report_month, report_month_source = infer_report_month(path, df, config)
    report_start, report_end = build_report_periods(report_month)
    df["report_month"] = report_month
    df["report_period_start"] = report_start
    df["report_period_end"] = report_end
    df["source_file"] = path.name

    volume_source_name = column_sources.get("volume")
    apply_volume_and_unit(df, volume_source_name, config, warnings)

    missing_critical = [
        col for col in CRITICAL_COLUMNS if col not in df.columns or df[col].isna().all()
    ]

    file_log.update(
        {
            "report_month": report_month,
            "report_month_source": report_month_source,
            "report_period_start": report_start,
            "report_period_end": report_end,
            "rows": int(len(df)),
            "unique_facility_codes": int(df["facility_code"].nunique(dropna=True))
            if "facility_code" in df.columns
            else 0,
            "missing_critical_columns": missing_critical,
            "selected_sheet": selected_sheet,
            "header_row": header_row,
            "matched_fields": matched_fields,
            "warnings": warnings,
            "status": "processed",
        }
    )

    return df, file_log


def ingest_all_excels(
    input_dir: Path,
    config: dict,
) -> Tuple[Optional[pd.DataFrame], dict]:
    files = list_excel_files(input_dir)
    log = {
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_dir": str(input_dir),
        "files_total": len(files),
        "files_processed": 0,
        "files_skipped": 0,
        "months_covered": [],
        "errors": [],
        "warnings": [],
        "file_logs": [],
    }

    if not files:
        return None, log

    column_synonyms = build_column_synonyms(config)
    header_tokens = config.get("header_tokens", DEFAULT_HEADER_TOKENS)

    combined: List[pd.DataFrame] = []
    months: List[str] = []

    for path in files:
        df, file_log = ingest_one_excel(path, config, column_synonyms, header_tokens)
        if df is None:
            log["files_skipped"] += 1
            log["errors"].append(file_log.get("error"))
            log["file_logs"].append(file_log)
            print(f"SKIP: {path.name} | {file_log.get('error')}")
            continue

        log["files_processed"] += 1
        log["file_logs"].append(file_log)
        if file_log.get("report_month"):
            months.append(file_log["report_month"])

        combined.append(df)

        missing = ", ".join(file_log.get("missing_critical_columns") or []) or "none"
        print(
            "Quality: {file} | rows={rows} | report_month={month} ({source}) | "
            "facility_codes={fac} | missing_critical={missing}".format(
                file=path.name,
                rows=file_log["rows"],
                month=file_log.get("report_month") or "UNKNOWN",
                source=file_log.get("report_month_source") or "unknown",
                fac=file_log.get("unique_facility_codes"),
                missing=missing,
            )
        )

        for warn in file_log.get("warnings", []):
            print(f"  WARN: {warn}")

    log["months_covered"] = sorted(set(months))
    if combined:
        df_all = pd.concat(combined, ignore_index=True)
    else:
        df_all = None
    return df_all, log


def write_data_dictionary(path: Path, columns: List[str]) -> None:
    column_descriptions = {
        "report_month": "Report month inferred from date_raw or filename (YYYY-MM).",
        "source_file": "Original Excel filename.",
        "report_period_start": "Month start date (YYYY-MM-01).",
        "report_period_end": "Month end date (YYYY-MM-DD).",
        "date_raw": "Original Date column value from Excel (often a month label).",
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
        "- report_month is inferred from date_raw when available to avoid filename drift.\n"
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
        help="Path to config YAML (optional).",
    )
    parser.add_argument(
        "--input_dir",
        "--input-dir",
        dest="input_dir",
        type=Path,
        default=None,
        help="Override input directory from config.",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=Path,
        default=None,
        help="Output CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=Path,
        default=None,
        help="Optional directory for extra outputs (log, dictionary, parquet).",
    )

    args = parser.parse_args()

    config = load_config(args.config) if args.config else {}

    input_dir = args.input_dir or Path(config.get("input_dir", DEFAULT_INPUT_DIR))
    if not input_dir.exists() and DEFAULT_INPUT_DIR.exists() and args.input_dir is None:
        input_dir = DEFAULT_INPUT_DIR

    output_path = args.output or Path(config.get("output_path", DEFAULT_OUTPUT_PATH))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_dir = args.output_dir or Path(config.get("output_dir", output_path.parent))
    output_dir.mkdir(parents=True, exist_ok=True)

    df_all, log = ingest_all_excels(input_dir, config)
    if df_all is None or df_all.empty:
        print(f"No data processed from {input_dir}.")
        return 1

    df_all = df_all[CANONICAL_COLUMNS]
    df_all.to_csv(output_path, index=False)

    # Optional extra outputs for backward compatibility.
    output_cfg = config.get("output", {})
    if output_cfg:
        output_long = output_dir / output_cfg.get("long_filename", "unit_volume_long.csv")
        df_all.to_csv(output_long, index=False)

        output_parquet = output_dir / output_cfg.get("parquet_filename", "unit_volume.parquet")
        try:
            df_all.to_parquet(output_parquet, index=False)
        except Exception as exc:
            msg = f"Parquet write skipped: {exc}"
            print(f"WARN: {msg}")
            log["warnings"].append(msg)

        wide_cfg = config.get("wide_output", {})
        if wide_cfg.get("enabled", True):
            group_by = wide_cfg.get("group_by", ["facility_code", "category", "unit"])
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
                output_wide = output_dir / output_cfg.get("wide_filename", "unit_volume_wide.csv")
                wide.to_csv(output_wide, index=False)
            else:
                msg = "Wide output skipped: missing report_month or group_by columns."
                print(f"WARN: {msg}")
                log["warnings"].append(msg)

    data_dict_path = output_dir / "data_dictionary.md"
    write_data_dictionary(data_dict_path, CANONICAL_COLUMNS)

    log["row_count"] = int(len(df_all))
    log_path = output_dir / "ingestion_log.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    # Self-checks to prevent silent month/facility loss.
    missing_months = df_all["report_month"].isna().sum()
    if missing_months:
        print(f"ERROR: report_month is null for {missing_months} rows.")
        return 2
    if "facility_code" not in df_all.columns or df_all["facility_code"].isna().all():
        print("ERROR: facility_code is missing or entirely null.")
        return 2

    print("\nSummary")
    print(f"- Files processed: {log['files_processed']} / {log['files_total']}")
    print(f"- Files skipped: {log['files_skipped']}")
    print(f"- Months covered: {', '.join(log['months_covered']) or 'none'}")
    print(f"- Total rows: {log['row_count']}")
    print(f"- Output CSV: {output_path}")
    print(f"- Output folder: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
