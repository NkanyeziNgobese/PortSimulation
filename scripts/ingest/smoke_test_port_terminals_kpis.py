#!/usr/bin/env python
"""
Smoke test for KPI extraction:
- Runs extraction for one year (prefer 2020 if present).
- Prints row counts and first 10 rows.
- If "DCT - Pier 1" and "DCT - Pier 2" exist in the PDF text, asserts they appear in extracted rows.
"""

from pathlib import Path

import pandas as pd
import pdfplumber

from ingest_port_terminals_kpis import (
    YEARS,
    BASE_DIR,
    find_pdf_for_year,
    extract_kpis_from_pdf,
)


def find_available_year() -> int:
    preferred = 2020
    pdf_path, _ = find_pdf_for_year(preferred, BASE_DIR)
    if pdf_path:
        return preferred

    for year in YEARS:
        pdf_path, _ = find_pdf_for_year(year, BASE_DIR)
        if pdf_path:
            return year
    raise FileNotFoundError("No Port Terminals PDF found for any year.")


def normalize_text(text: str) -> str:
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
    )


def pdf_contains_terms(pdf_path: Path, terms) -> dict:
    results = {term: False for term in terms}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = normalize_text(page.extract_text() or "")
            for term in terms:
                if term in text:
                    results[term] = True
    return results


def main() -> int:
    year = find_available_year()
    pdf_path, match_type = find_pdf_for_year(year, BASE_DIR)
    print(f"Running smoke test for {year} ({match_type}) -> {pdf_path}")

    rows, meta = extract_kpis_from_pdf(pdf_path, year)
    df = pd.DataFrame(rows)

    print(f"Rows extracted: {len(df)}")
    print(df.head(10))

    terms = ["DCT - Pier 1", "DCT - Pier 2"]
    term_presence = pdf_contains_terms(pdf_path, terms)

    for term, present in term_presence.items():
        if present:
            matches = df[
                df["terminal_or_scope"].fillna("").str.contains(term, na=False)
                | df["kpi_name"].fillna("").str.contains(term, na=False)
            ]
            assert not matches.empty, f"Expected to find rows for term: {term}"
            print(f"Found rows for term: {term}")
        else:
            print(f"Term not found in PDF text (skipping assert): {term}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
