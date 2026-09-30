"""Rebuild everything from the raw data in one command.

    python run_all.py

Steps: download the data if it is missing, profile it, run the SQL pipeline, validate
SQL against the independent Python rebuild, write the results report, build the
dashboard, take screenshots, check the write-ups against the outputs, run the tests.
Any failing step stops the build.
"""
from __future__ import annotations

import subprocess
import sys
import time

from src import (build_dashboard, check_docs, download_data, profile_data, report, run_sql,
                 screenshot, validate)
from src.paths import ROOT

STEPS = [
    ("Download raw data", download_data.main),
    ("Profile the data", profile_data.main),
    ("Run SQL pipeline (DuckDB)", run_sql.main),
    ("Validate SQL against Python", validate.main),
    ("Write results report", report.main),
    ("Build Plotly dashboard", build_dashboard.main),
    ("Take dashboard screenshots", screenshot.main),
    ("Check numbers quoted in the write-ups", check_docs.main),
]


def main() -> None:
    if sys.version_info[:2] != (3, 11):
        print(f"Note: built and tested on Python 3.11, running on "
              f"{sys.version_info.major}.{sys.version_info.minor}")
    start = time.time()
    for number, (name, step) in enumerate(STEPS, start=1):
        print(f"\n[{number}/{len(STEPS) + 1}] {name}")
        step()

    print(f"\n[{len(STEPS) + 1}/{len(STEPS) + 1}] Run tests")
    result = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT)
    if result.returncode != 0:
        sys.exit("Tests failed")
    print(f"\nBuild complete in {time.time() - start:.0f} seconds")


if __name__ == "__main__":
    main()
