"""Check that every number quoted in the write-ups comes from the pipeline outputs.

Rule: a number in docs/memo.md, RESUME_BULLETS.md or README.md must appear in
outputs/headline_numbers.json, or be one of a short list of structural numbers
(counts of things in the document, tenure band edges, the Python version).
Also checks that each resume bullet is at most 30 words and that the write-ups
contain no em-dashes.
"""
from __future__ import annotations

import json
import re
import sys

from src.paths import DOCS_DIR, OUTPUTS_DIR, ROOT

CHECKED_FILES = [DOCS_DIR / "memo.md", ROOT / "RESUME_BULLETS.md", ROOT / "README.md"]
STYLE_FILES = CHECKED_FILES + [ROOT / "INTERVIEW_PREP.md", ROOT / "ASSUMPTIONS.md",
                               ROOT / "PLAN.md", ROOT / "powerbi" / "POWERBI_BUILD_GUIDE.md"]
MAX_BULLET_WORDS = 30

NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:%|M\b|K\b)?")

# Numbers that describe the document or the method, not the data.
STRUCTURAL = {
    "1", "2", "3", "4", "5", "6", "8", "9", "10",   # list positions, counts of pages and factors
    "12",                                           # 12-month totals
    "13", "24", "25", "36", "37", "48", "49",       # tenure band edges
    "30",                                           # word limit for resume bullets
    "3.11",                                         # Python version
}

# Text that is not prose: code, links, and labels that contain digits.
STRIP = [
    re.compile(r"```.*?```", re.S),          # fenced code blocks
    re.compile(r"`[^`]*`"),                  # inline code
    re.compile(r"\]\([^)]*\)"),              # link targets
    re.compile(r"https?://\S+"),
    re.compile(r"\bQ[1-4]\b"),               # quarter labels
    re.compile(r"\b1e-6\b"),                 # validation tolerance
]


def clean(token: str) -> str:
    return token.rstrip(",.")


def allowed_numbers() -> set[str]:
    facts = json.loads((OUTPUTS_DIR / "headline_numbers.json").read_text(encoding="utf-8"))
    found: set[str] = set()
    for value in facts.values():
        found.update(clean(t) for t in NUMBER.findall(value))
    return found | STRUCTURAL


def numbers_in(text: str) -> list[str]:
    for pattern in STRIP:
        text = pattern.sub(" ", text)
    return [clean(t) for t in NUMBER.findall(text)]


def check_numbers(allowed: set[str]) -> list[str]:
    problems = []
    for path in CHECKED_FILES:
        text = path.read_text(encoding="utf-8")
        unknown = sorted({t for t in numbers_in(text) if t not in allowed})
        if unknown:
            problems.append(f"{path.name}: numbers not found in headline_numbers.json: "
                            + ", ".join(unknown))
    return problems


def check_resume_bullets() -> list[str]:
    text = (ROOT / "RESUME_BULLETS.md").read_text(encoding="utf-8")
    bullets = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    problems = []
    if len(bullets) != 2:
        problems.append(f"RESUME_BULLETS.md: expected 2 bullets, found {len(bullets)}")
    for bullet in bullets:
        words = len(bullet.split())
        if words > MAX_BULLET_WORDS:
            problems.append(f"RESUME_BULLETS.md: bullet has {words} words, limit is "
                            f"{MAX_BULLET_WORDS}: {bullet[:50]}...")
    return problems


def check_style() -> list[str]:
    dashes = (chr(0x2014), chr(0x2013))  # em-dash and en-dash, written as code points
    problems = []
    for path in dict.fromkeys(STYLE_FILES + sorted(DOCS_DIR.glob("*.md"))):
        if path.exists() and any(d in path.read_text(encoding="utf-8") for d in dashes):
            problems.append(f"{path.name}: contains an em-dash or en-dash")
    return problems


def main() -> None:
    problems = check_numbers(allowed_numbers()) + check_resume_bullets() + check_style()
    if problems:
        sys.exit("Document check failed:\n  " + "\n  ".join(problems))
    print(f"Document check passed: {len(CHECKED_FILES)} files, every quoted number is in "
          f"headline_numbers.json")


if __name__ == "__main__":
    main()
