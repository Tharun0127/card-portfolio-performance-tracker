"""Shared fixtures."""
import duckdb
import pytest

from src.paths import RAW_CSV
from src.run_sql import MODELS, build_model, configure


@pytest.fixture(scope="session")
def pipeline_db():
    """The full SQL pipeline built in memory from the raw file."""
    if not RAW_CSV.exists():
        pytest.skip(f"Raw data not found at {RAW_CSV}. Run: python -m src.download_data")
    con = duckdb.connect(":memory:")
    configure(con)
    for model in MODELS:
        build_model(con, model)
    yield con
    con.close()
