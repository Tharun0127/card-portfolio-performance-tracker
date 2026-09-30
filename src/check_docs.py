"""Check that every number quoted in the write-ups comes from the pipeline outputs.

Rule: a number in docs/memo.md or README.md must appear in
outputs/headline_numbers.json or in docs/proof/build_log.txt (both written by the
pipeline), or be one of a short list of structural numbers (counts of things in the
document, tenure band edges, the Python version).

Notes kept in the git-ignored private/ folder are checked the same way when present.
The write-ups must also contain no em-dashes.
"""
from __future__ import annotations

import json
import re
import sys

from src.paths import DOCS_DIR, OUTPUTS_DIR, ROOT

PRIVATE_DIR = ROOT / "private"
BUILD_LOG = DOCS_DIR / "proof" / "build_log.txt"
CHECKED_FILES = [DOCS_DIR / "memo.md", ROOT / "README.md", PRIVATE_DIR / "RESUME_BULLETS.md"]
STYLE_FILES = CHECKED_FILES + [PRIVATE_DIR / "INTERVIEW_PREP.md", ROOT / "ASSUMPTIONS.md",
                               ROOT / "PLAN.md", ROOT / "powerbi" / "POWERBI_BUILD_GUIDE.md"]
MAX_BULLET_WORDS = 30

# A number that is not glued to a preceding letter, so names with digits are not numbers.
NUMBER = re.compile(r"(?<![A-Za-z\d])\$?\d[\d,]*(?:\.\d+)?(?:%|M\b|K\b)?")

# Numbers that describe the document or the method, not the data.
STRUCTURAL = {
    "1", "2", "3", "4", "5", "6", "8", "9", "10",   # list positions, counts of pages and factors
    "12",                                           # 12-month totals
    "13", "24", "25", "36", "37", "48", "49",       # tenure band edges
    "30",                                           # word limit for short bullets
    "3.11",                                         # Python version
}

# Text that is not prose: code, links, and labels that contain digits.
STRIP = [
    re.compile(r"```.*?```", re.S),          # fenced code blocks
    re.compile(r"`[^`]*`"),                  # inline code
    re.compile(r"\]\([^)]*\)"),              # link targets
    re.compile(r"<[^>]+>"),                  # html tags (image sizes, anchors)
    re.compile(r"https?://\S+"),
    re.compile(r"\bQ[1-4]\b"),               # quarter labels
    re.compile(r"\b1e-6\b"),                 # validation tolerance
]


def clean(token: str) -> str:
    return token.rstrip(",.")


def allowed_numbers() -> set[str]:
    facts = json.loads((OUTPUTS_DIR / "headline_numbers.json").read_text(encoding="utf-8"))
    sources = list(facts.values())
    if BUILD_LOG.exists():
        sources.append(BUILD_LOG.read_text(encoding="utf-8"))
    found: set[str] = set()
    for value in sources:
        found.update(clean(t) for t in NUMBER.findall(value))
    return found | STRUCTURAL


def numbers_in(text: str) -> list[str]:
    for pattern in STRIP:
        text = pattern.sub(" ", text)
    return [clean(t) for t in NUMBER.findall(text)]


def check_numbers(allowed: set[str]) -> list[str]:
    problems = []
    for path in CHECKED_FILES:
        if not path.exists():
            continue
        unknown = sorted({t for t in numbers_in(path.read_text(encoding="utf-8"))
                          if t not in allowed})
        if unknown:
            problems.append(f"{path.name}: numbers not produced by the pipeline: "
                            + ", ".join(unknown))
    return problems


def check_bullet_length() -> list[str]:
    path = PRIVATE_DIR / "RESUME_BULLETS.md"
    if not path.exists():
        return []
    bullets = [line[2:].strip() for line in path.read_text(encoding="utf-8").splitlines()
               if line.startswith("- ")]
    return [f"{path.name}: bullet has {len(b.split())} words, limit is {MAX_BULLET_WORDS}"
            for b in bullets if len(b.split()) > MAX_BULLET_WORDS]


def check_style() -> list[str]:
    dashes = (chr(0x2014), chr(0x2013))  # em-dash and en-dash, written as code points
    problems = []
    for path in dict.fromkeys(STYLE_FILES + sorted(DOCS_DIR.glob("*.md"))):
        if path.exists() and any(d in path.read_text(encoding="utf-8") for d in dashes):
            problems.append(f"{path.name}: contains an em-dash or en-dash")
    return problems


def main() -> None:
    problems = check_numbers(allowed_numbers()) + check_bullet_length() + check_style()
    if problems:
        sys.exit("Document check failed:\n  " + "\n  ".join(problems))
    print("Document check passed: every number quoted in the write-ups is produced by "
          "the pipeline")


if __name__ == "__main__":
    main()
