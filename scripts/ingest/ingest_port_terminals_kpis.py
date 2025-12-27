#!/usr/bin/env python
"""
Dependencies
- Python 3.9+
- pandas
- pdfplumber
- camelot (optional fallback)
- pyarrow (optional, for parquet output)

Observed structure (sampled before coding)
- 2020: "Port Terminals 2020.pdf" (page with KPI table contains heading and a 4-period table)
  - Text lines include: "Overview of key performance indicators"
  - Header lines: year row (e.g., "2019 2020 2020 2021") and a status row
  - KPI table spans multiple pages (page break before "Financial performance review")
- 2023: "Transnet Port Terminals Report.pdf" (page with KPI table contains heading and a 9-period table)
  - Header line: "Key performance area and indicatorUnit of measure Actual Actual ..."
  - Periods include multiple years and targets/actuals
  - KPI rows are readable from extracted text lines

How to test (numbered steps)
1) Ensure annual PDFs exist under data/reports/annual_results/<year>/annual/.
2) From repo root, run: python scripts/ingest/ingest_port_terminals_kpis.py
3) Inspect data/processed/port_terminals_kpis for outputs and ingestion_log.json.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "pdfplumber is required. Install with: python -m pip install pdfplumber"
    ) from exc

try:
    import camelot  # type: ignore
except Exception:
    camelot = None


YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
BASE_DIR = Path("data/reports/annual_results")
OUTPUT_DIR = Path("data/processed/port_terminals_kpis")
OUTPUT_LONG_CSV = OUTPUT_DIR / "port_terminals_kpis_long.csv"
OUTPUT_LONG_PARQUET = OUTPUT_DIR / "port_terminals_kpis_long.parquet"
LOG_PATH = OUTPUT_DIR / "ingestion_log.json"

SECTION_HEADING = "overview of key performance indicators"
HEADER_HINTS = [
    "key performance area and indicator",
    "key performance area",
]

SECTION_NAMES = {
    "financial sustainability",
    "capacity creation and maintenance",
    "operational performance",
    "operational efficiency and productivity",
    "sustainable developmental outcomes",
    "operational performance continued",
    "financial sustainability continued",
}

STOP_KEYWORDS = {
    "financial performance review",
    "performance commentary",
    "financial performance",
}

UNIT_PHRASES = [
    "moves per gross crane hour",
    "moves per ship working hour",
    "moves per hour",
    "tons per hour",
    "tonnes per hour",
    "million tons",
    "million tonnes",
    "000 teus",
    "000 teu",
    "'000 teus",
    "teus",
    "teu",
    "r million",
    "minutes",
    "hours",
    "days",
    "units",
    "number",
    "mt",
    "%",
]

TERMINAL_MARKERS = [
    r"\bDCT\b",
    r"\bCTCT\b",
    r"\bNCT\b",
    r"\bPE\b",
    r"\bPier\b",
    r"Durban",
    r"Richards Bay",
    r"Saldanha",
    r"RB DBT",
    r"Port Elizabeth",
]

VALUE_PATTERN = re.compile(
    r"(?:n/?a|N/?A)|\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d+)?"
)


@dataclass
class ParseState:
    current_section: Optional[str] = None
    current_kpi: Optional[str] = None


def normalize_text(value: str) -> str:
    text = str(value).strip().lower()
    text = text.replace("\n", " ")
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2022", "-")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_line(value: str) -> str:
    text = str(value).replace("\u2013", "-").replace("\u2014", "-").replace("\u2022", "-")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return text


def clean_kpi_name(value: str) -> str:
    text = value.strip()
    text = re.sub(r"\s+", " ", text)
    # Remove trailing footnote numbers (e.g., "turnaround time3") but keep pier numbers.
    if not looks_like_terminal(text):
        text = re.sub(r"(\D)\d+$", r"\1", text).strip()
    return text


def normalize_unit_text(unit: str) -> str:
    text = unit.replace("\u2019", "'").replace("\u2018", "'")
    return text


def looks_like_terminal(text: str) -> bool:
    for pattern in TERMINAL_MARKERS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def find_pdf_for_year(year: int, base_dir: Path) -> Tuple[Optional[Path], str]:
    annual_dir = base_dir / str(year) / "annual"
    if not annual_dir.exists():
        return None, "missing_year_folder"

    expected = annual_dir / f"Port Terminals {year}.pdf"
    if expected.exists():
        return expected, "exact"

    candidates = list(annual_dir.glob("*.pdf"))
    if not candidates:
        return None, "no_pdfs"

    # Fallback: any file containing "Port Terminals" and year
    year_match = [
        p
        for p in candidates
        if "port terminals" in p.name.lower() and str(year) in p.name
    ]
    if len(year_match) == 1:
        return year_match[0], "fallback_year_match"

    # Fallback: any file containing "Port Terminals"
    term_match = [p for p in candidates if "port terminals" in p.name.lower()]
    if len(term_match) == 1:
        return term_match[0], "fallback_single_terminals"

    return None, "not_found"


def parse_period_labels(lines: Iterable[str]) -> List[str]:
    year_line = None
    status_line = None
    max_years = 0
    max_status = 0

    for line in lines:
        years = re.findall(r"20\d{2}", line)
        if len(years) > max_years:
            max_years = len(years)
            year_line = line

        statuses = re.findall(r"(Actual|Target|Budget|Forecast)", line, re.IGNORECASE)
        if len(statuses) > max_status:
            max_status = len(statuses)
            status_line = line

    years = [int(y) for y in re.findall(r"20\d{2}", year_line or "")]
    statuses = [
        s.capitalize()
        for s in re.findall(r"(Actual|Target|Budget|Forecast)", status_line or "", re.IGNORECASE)
    ]

    if years and statuses and len(years) == len(statuses):
        return [f"{y} {s}" for y, s in zip(years, statuses)]
    if years and not statuses:
        return [str(y) for y in years]
    if years and statuses:
        # Fallback: align by shortest length and keep remaining year labels
        labels = [f"{y} {s}" for y, s in zip(years, statuses)]
        for y in years[len(statuses):]:
            labels.append(str(y))
        return labels

    return []


def extract_values_from_line(line: str, num_periods: int) -> Tuple[Optional[str], List[str]]:
    matches = list(VALUE_PATTERN.finditer(line))
    if len(matches) < num_periods or num_periods == 0:
        return None, []

    chosen = matches[-num_periods:]
    start = chosen[0].start()
    left_text = line[:start].strip()
    values = [m.group(0) for m in chosen]
    return left_text, values


def parse_value(value: str) -> Optional[float]:
    if value is None:
        return None
    text = value.strip()
    if text.lower() in {"n/a", "na", "-", "\u2013"}:
        return None
    text = text.replace(" ", "")
    # Use comma as decimal separator if no dot is present
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    text = text.replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def extract_unit(left_text: str) -> Tuple[str, Optional[str]]:
    cleaned = left_text.strip()
    cleaned = normalize_line(cleaned)
    for unit in sorted(UNIT_PHRASES, key=len, reverse=True):
        pattern = re.compile(rf"(?:^|\s){re.escape(unit)}$", re.IGNORECASE)
        if pattern.search(cleaned):
            name = pattern.sub("", cleaned).strip()
            return name, normalize_unit_text(unit)
    return cleaned, None


def should_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.isdigit():
        return True
    lower = stripped.lower()
    if "transnet port terminals" in lower or lower.startswith("transnet port terminals"):
        return True
    if lower.startswith("transnet port terminals"):
        return True
    if lower.startswith("port terminals"):
        return True
    if lower.startswith("contents"):
        return True
    if lower.startswith("operational performance continued"):
        return True
    return False


def is_header_hint(line: str) -> bool:
    norm = normalize_text(line)
    return any(hint in norm for hint in HEADER_HINTS)


def build_rows_from_lines(
    lines: List[str],
    period_labels: List[str],
    state: ParseState,
    year: int,
    source_pdf: str,
    page_number: int,
) -> List[dict]:
    rows: List[dict] = []
    num_periods = len(period_labels)

    for line in lines:
        if should_skip_line(line):
            continue

        norm = normalize_text(line)
        if SECTION_HEADING in norm or is_header_hint(line):
            continue
        if any(stop in norm for stop in STOP_KEYWORDS):
            break

        if re.fullmatch(r"(20\d{2}\s+)+20\d{2}", norm):
            continue

        line = normalize_line(line)
        left_text, values = extract_values_from_line(line, num_periods)
        if not values:
            # Heading line
            heading = clean_kpi_name(line)
            if normalize_text(heading) in SECTION_NAMES:
                state.current_section = heading
                state.current_kpi = None
            else:
                state.current_kpi = heading
            continue

        # Parse values
        parsed_values = [parse_value(v) for v in values]

        # Extract unit and the descriptive text
        descriptive, unit = extract_unit(left_text or "")
        descriptive = clean_kpi_name(descriptive)

        bullet = bool(re.match(r"^[\u2013\u2014\-\u2022]+", descriptive))
        descriptive = re.sub(r"^[\u2013\u2014\-\u2022]+\s*", "", descriptive).strip()

        kpi_name = state.current_kpi or descriptive
        terminal_or_scope = None
        submetric = None

        if bullet:
            if looks_like_terminal(descriptive):
                terminal_or_scope = descriptive
            else:
                submetric = descriptive
        else:
            if state.current_kpi and looks_like_terminal(descriptive):
                terminal_or_scope = descriptive
            elif state.current_kpi and descriptive and descriptive != state.current_kpi:
                kpi_name = descriptive
                state.current_kpi = descriptive
            else:
                kpi_name = descriptive or state.current_kpi

        if kpi_name:
            kpi_name = clean_kpi_name(kpi_name)

        # Map period labels to the fixed output columns
        period_pairs = list(zip(period_labels, parsed_values))
        period_left = period_pairs[0] if len(period_pairs) > 0 else (None, None)
        period_mid = period_pairs[1] if len(period_pairs) > 1 else (None, None)
        period_right = period_pairs[2] if len(period_pairs) > 2 else (None, None)
        period_next = period_pairs[3] if len(period_pairs) > 3 else (None, None)
        extras = period_pairs[4:] if len(period_pairs) > 4 else []

        confidence = 0.4
        if state.current_section:
            confidence += 0.2
        if unit:
            confidence += 0.2
        if len(period_labels) == len(parsed_values):
            confidence += 0.2
        confidence = min(confidence, 1.0)

        rows.append(
            {
                "report_year": year,
                "kpi_section": state.current_section,
                "kpi_name": kpi_name,
                "terminal_or_scope": terminal_or_scope,
                "submetric": submetric,
                "unit": unit,
                "period_left_label": period_left[0],
                "period_left_value": period_left[1],
                "period_mid_label": period_mid[0],
                "period_mid_value": period_mid[1],
                "period_right_label": period_right[0],
                "period_right_value": period_right[1],
                "period_next_label": period_next[0],
                "period_next_value": period_next[1],
                "period_extra_labels": json.dumps([e[0] for e in extras]) if extras else None,
                "period_extra_values": json.dumps([e[1] for e in extras]) if extras else None,
                "source_pdf": source_pdf,
                "source_page_start": page_number,
                "source_page_end": page_number,
                "extraction_confidence": round(confidence, 2),
            }
        )

    return rows


def extract_kpis_from_pdf(pdf_path: Path, year: int) -> Tuple[List[dict], dict]:
    meta = {
        "year": year,
        "pdf": str(pdf_path),
        "start_page": None,
        "end_page": None,
        "rows_extracted": 0,
        "warnings": [],
    }

    rows: List[dict] = []
    page_count = 0
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        start_page = None
        for i, page in enumerate(pdf.pages):
            text = normalize_line(page.extract_text() or "")
            lower = text.lower()
            if "contents" in lower and i <= 2:
                continue
            has_heading = SECTION_HEADING in lower
            has_header = any(hint in lower for hint in HEADER_HINTS)
            year_count = len(re.findall(r"20\d{2}", lower))
            if has_heading and (has_header or year_count >= 3):
                start_page = i
                break
            if start_page is None and has_header and year_count >= 3:
                start_page = i
        if start_page is None:
            meta["warnings"].append("KPI header not found.")
            return rows, meta

        period_labels: List[str] = []
        state = ParseState()

        for i in range(start_page, len(pdf.pages)):
            page = pdf.pages[i]
            text = normalize_line(page.extract_text() or "")
            lower = text.lower()

            if i == start_page:
                meta["start_page"] = i + 1

            # Stop conditions
            if i > start_page and any(stop in lower for stop in STOP_KEYWORDS):
                meta["end_page"] = i
                break

            lines = text.splitlines()

            # If header line exists, refresh period labels from this page
            if any(hint in lower for hint in HEADER_HINTS) or not period_labels:
                period_labels = parse_period_labels(lines)

            # Start parsing after heading or header line
            start_idx = 0
            for idx, line in enumerate(lines):
                if SECTION_HEADING in normalize_text(line):
                    start_idx = idx + 1
                if is_header_hint(line):
                    start_idx = max(start_idx, idx + 1)
            page_lines = lines[start_idx:]

            page_rows = build_rows_from_lines(
                page_lines,
                period_labels,
                state,
                year,
                str(pdf_path),
                i + 1,
            )

            if page_rows:
                rows.extend(page_rows)
                meta["end_page"] = i + 1
            elif i > start_page and meta["end_page"] is not None:
                break

    # Optional fallback: use camelot if pdfplumber yields no rows but we have a start page.
    if not rows and camelot is not None and meta.get("start_page"):
        try:
            pages = ",".join(
                str(p)
                for p in range(
                    meta["start_page"], min(meta["start_page"] + 3, page_count + 1)
                )
            )
            tables = camelot.read_pdf(str(pdf_path), pages=pages, flavor="stream")
            for table in tables:
                df_table = table.df
                lines = [
                    " ".join(str(v) for v in row if str(v).strip() != "")
                    for row in df_table.values.tolist()
                ]
                rows.extend(
                    build_rows_from_lines(
                        lines,
                        period_labels,
                        ParseState(),
                        year,
                        str(pdf_path),
                        meta["start_page"],
                    )
                )
            if rows:
                meta["warnings"].append("Used camelot fallback extraction.")
        except Exception as exc:
            meta["warnings"].append(f"Camelot fallback failed: {exc}")

    meta["rows_extracted"] = len(rows)
    if not rows:
        meta["warnings"].append("No KPI rows extracted.")
    return rows, meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract KPI tables from Port Terminals annual PDFs."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=BASE_DIR,
        help="Base directory for annual results.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for extracted KPIs.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    log = {
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_dir": str(args.base_dir),
        "output_dir": str(output_dir),
        "years": {},
        "rows_total": 0,
        "warnings": [],
    }

    all_rows: List[dict] = []

    for year in YEARS:
        pdf_path, match_type = find_pdf_for_year(year, args.base_dir)
        year_log = {
            "year": year,
            "match_type": match_type,
            "pdf_path": str(pdf_path) if pdf_path else None,
            "rows_extracted": 0,
            "start_page": None,
            "end_page": None,
            "warnings": [],
        }

        if not pdf_path:
            year_log["warnings"].append("PDF not found.")
            log["years"][str(year)] = year_log
            print(f"{year}: PDF not found ({match_type}).")
            continue

        print(f"{year}: Extracting from {pdf_path.name} ({match_type})")
        rows, meta = extract_kpis_from_pdf(pdf_path, year)
        all_rows.extend(rows)

        year_log["rows_extracted"] = meta["rows_extracted"]
        year_log["start_page"] = meta.get("start_page")
        year_log["end_page"] = meta.get("end_page")
        year_log["warnings"].extend(meta.get("warnings", []))

        if meta.get("warnings"):
            log["warnings"].extend(meta["warnings"])

        log["years"][str(year)] = year_log
        print(
            f"  Rows: {year_log['rows_extracted']} | Pages: {year_log['start_page']}-{year_log['end_page']}"
        )

    if not all_rows:
        print("No KPI data extracted. See ingestion_log.json for details.")
        LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")
        return 1

    df = pd.DataFrame(all_rows)
    df.sort_values(by=["report_year", "kpi_section", "kpi_name"], inplace=True)
    df.to_csv(OUTPUT_LONG_CSV, index=False)

    try:
        df.to_parquet(OUTPUT_LONG_PARQUET, index=False)
    except Exception as exc:
        log["warnings"].append(f"Parquet write skipped: {exc}")

    log["rows_total"] = int(len(df))
    LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print("\nSummary")
    print(f"- Total rows: {len(df)}")
    print(f"- Output CSV: {OUTPUT_LONG_CSV}")
    print(f"- Output Parquet: {OUTPUT_LONG_PARQUET}")
    print(f"- Log: {LOG_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
