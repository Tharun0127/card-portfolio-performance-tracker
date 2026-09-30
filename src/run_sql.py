"""Run the SQL models in DuckDB and export the marts to CSV.

Each file in sql/ holds one SELECT statement. The runner materialises it as a table
named after the file, in dependency order. This is the same convention dbt uses,
without the dependency on dbt.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from src.paths import DB_PATH, OUTPUTS_DIR, POWERBI_DIR, RAW_CSV, SQL_DIR

LOW_N_THRESHOLD = 50

# Dependency order: staging -> intermediate -> marts.
MODELS = [
    "staging/stg_customers",
    "intermediate/int_customer_segments",
    "intermediate/int_customer_quarters",
    "intermediate/int_customer_quarter_scenario",
    "marts/mart_cell_quarter",
    "marts/mart_cell_period",
    "marts/mart_decomposition",
    "marts/mart_decomposition_long",
    "marts/mart_segment_contribution",
    "marts/mart_mix_reconciliation",
    "marts/pbi_fact_customer_quarter",
    "marts/pbi_dim_customer",
    "marts/pbi_dim_tier",
    "marts/pbi_dim_tenure",
    "marts/pbi_dim_scenario",
    "marts/pbi_dim_bridge_step",
    "marts/pbi_expected_values",
]

ANALYSIS_EXPORTS = [
    "mart_cell_period",
    "mart_decomposition",
    "mart_decomposition_long",
    "mart_segment_contribution",
    "mart_mix_reconciliation",
]

POWERBI_EXPORTS = {
    "pbi_fact_customer_quarter": "fact_customer_quarter",
    "pbi_dim_customer": "dim_customer",
    "pbi_dim_tier": "dim_tier",
    "pbi_dim_tenure": "dim_tenure",
    "pbi_dim_scenario": "dim_scenario",
    "pbi_dim_bridge_step": "dim_bridge_step",
    "pbi_expected_values": "expected_values",
}


def read_model(model: str) -> str:
    return (SQL_DIR / f"{model}.sql").read_text(encoding="utf-8")


def configure(con: duckdb.DuckDBPyConnection, raw_csv: Path = RAW_CSV) -> None:
    """Session settings shared by the pipeline and the tests."""
    # One thread keeps row order and floating point sums identical from run to run.
    con.execute("set threads = 1")
    con.execute(f"set variable low_n_threshold = {LOW_N_THRESHOLD}")
    con.execute("set variable raw_csv_path = ?", [raw_csv.as_posix()])


def build_model(con: duckdb.DuckDBPyConnection, model: str) -> str:
    name = Path(model).name
    con.execute(f"create or replace table {name} as\n{read_model(model)}")
    return name


def export_csv(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"copy {table} to '{path.as_posix()}' (header, delimiter ',')")


def main() -> None:
    if not RAW_CSV.exists():
        raise SystemExit(f"Raw data not found at {RAW_CSV}. Run: python -m src.download_data")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    try:
        configure(con)
        for model in MODELS:
            name = build_model(con, model)
            rows = con.execute(f"select count(*) from {name}").fetchone()[0]
            print(f"  built {name:<32} {rows:>7,} rows")

        for table in ANALYSIS_EXPORTS:
            export_csv(con, table, OUTPUTS_DIR / f"{table}.csv")
        for table, filename in POWERBI_EXPORTS.items():
            export_csv(con, table, POWERBI_DIR / f"{filename}.csv")
    finally:
        con.close()
    print(f"Exported marts to {OUTPUTS_DIR} and star schema to {POWERBI_DIR}")


if __name__ == "__main__":
    main()
