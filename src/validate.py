"""Check that the SQL marts and the independent Python rebuild agree within 1e-6.

Also checks the properties the write-ups rely on: effects add up to the spend change,
segment changes add up to the portfolio change, and the fact table reproduces the marts.
Any failure raises and stops run_all.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src.paths import DB_PATH, OUTPUTS_DIR
from src.python_pipeline import KEYS, build_decomposition

TOLERANCE = 1e-6

COMPARE_COLUMNS = [
    "customers_q1", "customers_q4", "active_q1", "active_q4",
    "txns_q1", "txns_q4", "spend_q1", "spend_q4", "delta_spend",
    "active_rate_q1", "active_rate_q4", "txns_per_active_q1", "txns_per_active_q4",
    "avg_ticket_q1", "avg_ticket_q4",
    "effect_customers", "effect_active_rate", "effect_txns_per_active", "effect_avg_ticket",
    "lmdi_customers", "lmdi_active_rate", "lmdi_txns_per_active", "lmdi_avg_ticket",
    "seq_customers", "seq_active_rate", "seq_txns_per_active", "seq_avg_ticket",
]


def compare_sql_to_python(sql: pd.DataFrame, py: pd.DataFrame) -> pd.DataFrame:
    """Max absolute difference per column. Raises if anything is off."""
    if len(sql) != len(py):
        raise AssertionError(f"Row counts differ: SQL {len(sql)}, Python {len(py)}")
    merged = sql.merge(py, on=KEYS, how="outer", suffixes=("_sql", "_py"), indicator=True)
    if not (merged["_merge"] == "both").all():
        raise AssertionError("SQL and Python produced different cells")

    if not (merged["decomposition_method_sql"] == merged["decomposition_method_py"]).all():
        raise AssertionError("SQL and Python disagree on where the fallback is used")
    if not (merged["is_low_n_sql"].astype(bool) == merged["is_low_n_py"].astype(bool)).all():
        raise AssertionError("SQL and Python disagree on the low-n flag")

    rows = []
    for col in COMPARE_COLUMNS:
        a = merged[f"{col}_sql"].astype(float)
        b = merged[f"{col}_py"].astype(float)
        if not (a.isna() == b.isna()).all():
            raise AssertionError(f"{col}: nulls in different places")
        diff = (a - b).abs().max()
        rows.append({"column": col, "max_abs_diff": 0.0 if pd.isna(diff) else float(diff)})
    report = pd.DataFrame(rows)
    worst = report.loc[report["max_abs_diff"].idxmax()]
    if worst["max_abs_diff"] > TOLERANCE:
        raise AssertionError(
            f"SQL and Python differ by {worst['max_abs_diff']:.3e} on {worst['column']}, "
            f"tolerance is {TOLERANCE}"
        )
    return report


def check_internal_consistency(con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    """Properties that must hold for the write-ups to be true."""
    checks: dict[str, float] = {}

    checks["max_abs_residual_effects_vs_change"] = con.execute(
        "select max(abs(residual)) from mart_decomposition").fetchone()[0]

    # Segments partition the book, so segment changes add up to the portfolio change.
    checks["max_abs_gap_segments_vs_portfolio"] = con.execute("""
        with seg as (
            select method, scenario, grain, fsum(delta_spend) as delta
            from mart_decomposition where grain <> 'portfolio'
            group by all
        )
        select max(abs(seg.delta - p.delta_spend))
        from seg
        inner join mart_decomposition as p
            on p.grain = 'portfolio' and p.method = seg.method and p.scenario = seg.scenario
    """).fetchone()[0]

    # The Power BI fact table must reproduce the base-case portfolio totals.
    checks["max_abs_gap_fact_vs_mart_spend"] = con.execute("""
        with fact as (
            select case scenario_key when 1 then 'A' else 'B' end as scenario,
                   fsum(spend) filter (where quarter = 'Q1') as spend_q1,
                   fsum(spend) filter (where quarter = 'Q4') as spend_q4,
                   count(*) filter (where quarter = 'Q4')    as customers_q4
            from pbi_fact_customer_quarter group by all
        )
        select max(greatest(abs(f.spend_q1 - m.spend_q1), abs(f.spend_q4 - m.spend_q4),
                            abs(f.customers_q4 - m.customers_q4)))
        from fact as f
        inner join mart_decomposition as m
            on m.grain = 'portfolio' and m.method = 'linear' and m.scenario = f.scenario
    """).fetchone()[0]

    for name, value in checks.items():
        if value is None or value > TOLERANCE:
            raise AssertionError(f"Consistency check failed: {name} = {value}")

    # Under the linear assumption Q1 + Q4 is half the 12-month total for every customer
    # whose ratios were not overridden, so the portfolio total is a useful sanity check.
    total, q1_q4 = con.execute("""
        select (select fsum(total_trans_amt) from stg_customers),
               (select spend_q1 + spend_q4 from mart_decomposition
                where grain = 'portfolio' and method = 'linear' and scenario = 'A')
    """).fetchone()
    checks["linear_q1_plus_q4_over_annual_total"] = q1_q4 / total
    if abs(q1_q4 / total - 0.5) > 1e-4:
        raise AssertionError("Linear assumption: Q1 + Q4 should be half the annual total")

    min_months = con.execute("select min(months_on_book) from stg_customers").fetchone()[0]
    if min_months < 13:
        raise AssertionError("Tenure below 13 months found: the '13-24' label would be wrong")
    return checks


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        sql = con.execute("select * from mart_decomposition").df()
        checks = check_internal_consistency(con)
    finally:
        con.close()

    report = compare_sql_to_python(sql, build_decomposition())
    report.to_csv(OUTPUTS_DIR / "sql_vs_python_check.csv", index=False,
                  lineterminator="\n")

    worst = report.loc[report["max_abs_diff"].idxmax()]
    print(f"  SQL vs Python: {len(sql)} cells, {len(report)} columns, "
          f"largest difference {worst['max_abs_diff']:.2e} on {worst['column']} "
          f"(tolerance {TOLERANCE})")
    for name, value in checks.items():
        print(f"  {name}: {value:.3e}")
    print("Validation passed")


if __name__ == "__main__":
    main()
