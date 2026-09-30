"""Project paths, defined once so every script agrees on where things live."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
RAW_CSV = RAW_DIR / "BankChurners.csv"

SQL_DIR = ROOT / "sql"
BUILD_DIR = ROOT / "build"
DB_PATH = BUILD_DIR / "portfolio.duckdb"

OUTPUTS_DIR = ROOT / "outputs"
POWERBI_DIR = ROOT / "powerbi"
DOCS_DIR = ROOT / "docs"

KAGGLE_DATASET = "sakshigoyal7/credit-card-customers"
