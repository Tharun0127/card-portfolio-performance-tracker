"""Run the SQL decomposition on small synthetic cells and compare with the Python functions.

The SQL model reads a table called mart_cell_period. Here that table is built by hand,
so the SQL logic is tested on cases with known answers, without the raw data.
"""
import duckdb
import pandas as pd
import pytest

from src.decomposition import decompose, factors_from_totals, sequential_effects
from src.run_sql import build_model, configure

# name: (customers, active, txns, spend) in Q1 then Q4
SYNTHETIC_CELLS = {
    "general":        ((1000, 800, 8000.0, 400000.0), (1100, 825, 9900.0, 445500.0)),
    "zero_change":    ((1000, 800, 8000.0, 400000.0), (1000, 800, 8000.0, 400000.0)),
    "only_customers": ((1000, 800, 8000.0, 400000.0), (500, 400, 4000.0, 200000.0)),
    "only_active":    ((1000, 800, 8000.0, 400000.0), (1000, 400, 4000.0, 200000.0)),
    "only_frequency": ((1000, 800, 8000.0, 400000.0), (1000, 800, 4000.0, 200000.0)),
    "only_ticket":    ((1000, 800, 8000.0, 400000.0), (1000, 800, 8000.0, 200000.0)),
    "all_leave":      ((1000, 800, 8000.0, 400000.0), (0, 0, 0.0, 0.0)),
    "none_active_q4": ((1000, 800, 8000.0, 400000.0), (1000, 0, 0.0, 0.0)),
}
EFFECTS = ["effect_customers", "effect_active_rate", "effect_txns_per_active",
           "effect_avg_ticket"]
SEQUENTIAL = ["seq_customers", "seq_active_rate", "seq_txns_per_active", "seq_avg_ticket"]


def synthetic_cell_period() -> pd.DataFrame:
    rows = []
    for name, (q1, q4) in SYNTHETIC_CELLS.items():
        f0, f1 = factors_from_totals(*q1), factors_from_totals(*q4)
        rows.append({
            "method": "linear", "scenario": "A", "grain": "test",
            "card_tier": name, "tenure_band": "All", "attrition_flag": "All",
            "segment": name,
            "customers_q1": q1[0], "customers_q4": q4[0],
            "active_q1": q1[1], "active_q4": q4[1],
            "txns_q1": q1[2], "txns_q4": q4[2],
            "spend_q1": q1[3], "spend_q4": q4[3],
            "n_q1": f0[0], "n_q4": f1[0],
            "active_rate_q1": f0[1], "active_rate_q4": f1[1],
            "txns_per_active_q1": f0[2], "txns_per_active_q4": f1[2],
            "avg_ticket_q1": f0[3], "avg_ticket_q4": f1[3],
            "is_low_n": False,
        })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def sql_result() -> pd.DataFrame:
    con = duckdb.connect(":memory:")
    configure(con)
    con.register("synthetic_cells", synthetic_cell_period())
    con.execute("create table mart_cell_period as select * from synthetic_cells")
    build_model(con, "marts/mart_decomposition")
    result = con.execute("select * from mart_decomposition").df().set_index("segment")
    con.close()
    return result


@pytest.mark.parametrize("name", SYNTHETIC_CELLS)
def test_sql_effects_sum_to_spend_change(sql_result, name):
    row = sql_result.loc[name]
    assert row[EFFECTS].sum() == pytest.approx(row["delta_spend"], abs=1e-6)
    assert abs(row["residual"]) < 1e-6


@pytest.mark.parametrize("name", SYNTHETIC_CELLS)
def test_sql_matches_python(sql_result, name):
    q1, q4 = SYNTHETIC_CELLS[name]
    f0, f1 = factors_from_totals(*q1), factors_from_totals(*q4)
    method, effects = decompose(f0, f1)
    row = sql_result.loc[name]
    assert row["decomposition_method"] == method
    assert list(row[EFFECTS]) == pytest.approx(effects, abs=1e-6)
    assert list(row[SEQUENTIAL]) == pytest.approx(sequential_effects(f0, f1), abs=1e-6)


def test_sql_zero_change_case(sql_result):
    row = sql_result.loc["zero_change"]
    assert list(row[EFFECTS]) == [0.0, 0.0, 0.0, 0.0]
    assert row["dominant_driver"] == "None"


@pytest.mark.parametrize("name, column, driver", [
    ("only_customers", "effect_customers", "Customers on book"),
    ("only_active", "effect_active_rate", "Active rate"),
    ("only_frequency", "effect_txns_per_active", "Transactions per active"),
    ("only_ticket", "effect_avg_ticket", "Average ticket"),
])
def test_sql_single_factor_change_case(sql_result, name, column, driver):
    row = sql_result.loc[name]
    assert row[column] == pytest.approx(-200000.0, abs=1e-6)
    others = [c for c in EFFECTS if c != column]
    assert all(abs(row[c]) < 1e-6 for c in others)
    assert row["dominant_driver"] == driver


@pytest.mark.parametrize("name, column", [
    ("all_leave", "effect_customers"),
    ("none_active_q4", "effect_active_rate"),
])
def test_sql_zero_factor_uses_flagged_fallback(sql_result, name, column):
    row = sql_result.loc[name]
    assert row["decomposition_method"] == "sequential_fallback"
    assert pd.isna(row["lmdi_customers"])
    assert row[column] == pytest.approx(-400000.0, abs=1e-6)
    assert row[EFFECTS].sum() == pytest.approx(-400000.0, abs=1e-6)
