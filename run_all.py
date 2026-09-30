"""Rebuild everything from the raw data in one command.

    python run_all.py

Steps: download the data if it is missing, profile it, run the SQL pipeline, validate
SQL against the independent Python rebuild, write the results report, build the
dashboard, take screenshots, run the tests, check the write-ups against the outputs.
Any failing step stops the build.

The output of the build is saved to docs/proof/build_log.txt so that the validation
and test results quoted in the README can be traced to a real run.
"""
from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
import time

from src import (build_dashboard, check_docs, download_data, profile_data, report, run_sql,
                 screenshot, validate)
from src.paths import DOCS_DIR, ROOT

BUILD_LOG = DOCS_DIR / "proof" / "build_log.txt"

# (name, function, include in the saved log)
STEPS = [
    ("Download raw data", download_data.main, False),  # message differs on first run
    ("Profile the data", profile_data.main, True),
    ("Run SQL pipeline (DuckDB)", run_sql.main, True),
    ("Validate SQL against Python", validate.main, True),
    ("Write results report", report.main, True),
    ("Build Plotly dashboard", build_dashboard.main, True),
    ("Take dashboard screenshots", screenshot.main, False),  # depends on a local browser
]


def normalise(text: str) -> str:
    """Make the log identical from run to run and from machine to machine."""
    text = text.replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "")
    text = text.replace("\\", "/")
    return re.sub(r" in \d+(\.\d+)?s\b", "", text)


def run_tests() -> str:
    result = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
                            cwd=ROOT, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit("Tests failed")
    return result.stdout


def write_log(sections: list[str]) -> None:
    BUILD_LOG.parent.mkdir(parents=True, exist_ok=True)
    header = ("Build log written by run_all.py. Paths are relative to the repository root.\n"
              "Timings are removed so the file only changes when the results change.\n")
    BUILD_LOG.write_text(header + "\n" + "\n".join(sections), encoding="utf-8", newline="\n")


def main() -> None:
    if sys.version_info[:2] != (3, 11):
        print(f"Note: built and tested on Python 3.11, running on "
              f"{sys.version_info.major}.{sys.version_info.minor}")
    start = time.time()
    total = len(STEPS) + 2
    sections: list[str] = []

    for number, (name, step, logged) in enumerate(STEPS, start=1):
        print(f"\n[{number}/{total}] {name}")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            step()
        print(buffer.getvalue(), end="")
        if logged:
            sections.append(f"== {name} ==\n{normalise(buffer.getvalue())}")

    print(f"\n[{total - 1}/{total}] Run tests")
    sections.append(f"== Run tests (pytest) ==\n{normalise(run_tests())}")
    write_log(sections)

    # Last, because the README may quote numbers from the log written just above.
    print(f"\n[{total}/{total}] Check numbers quoted in the write-ups")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        check_docs.main()
    print(buffer.getvalue(), end="")
    sections.append(f"== Check numbers quoted in the write-ups ==\n{buffer.getvalue()}")
    write_log(sections)

    print(f"\nBuild complete in {time.time() - start:.0f} seconds")


if __name__ == "__main__":
    main()
