"""Tests on the real data: the SQL pipeline against the independent Python rebuild."""
import pytest

from src.python_pipeline import build_decomposition
from src.validate import TOLERANCE, check_internal_consistency, compare_sql_to_python

EFFECTS = ["effect_customers", "effect_active_rate", "effect_txns_per_active",
           "effect_avg_ticket"]


@pytest.fixture(scope="module")
def decomposition(pipeline_db):
    return pipeline_db.execute("select * from mart_decomposition").df()


def test_sql_and_python_agree_within_tolerance(decomposition):
    report = compare_sql_to_python(decomposition, build_decomposition())
    assert report["max_abs_diff"].max() < TOLERANCE


def test_internal_consistency(pipeline_db):
    checks = check_internal_consistency(pipeline_db)
    assert checks["max_abs_residual_effects_vs_change"] < TOLERANCE
    assert checks["max_abs_gap_segments_vs_portfolio"] < TOLERANCE


def test_effects_sum_to_spend_change_in_every_cell(decomposition):
    gap = (decomposition[EFFECTS].sum(axis=1) - decomposition["delta_spend"]).abs()
    assert gap.max() < TOLERANCE


def test_raw_file_shape(pipeline_db):
    rows, customers = pipeline_db.execute(
        "select count(*), count(distinct customer_id) from stg_customers").fetchone()
    assert rows == customers == 10127
    columns = [r[0] for r in pipeline_db.execute("describe stg_customers").fetchall()]
    assert not any("naive_bayes" in c.lower() for c in columns)


def test_scenario_a_has_no_customer_effect(decomposition):
    a = decomposition[decomposition["scenario"] == "A"]
    assert (a["customers_q1"] == a["customers_q4"]).all()
    assert (a["effect_customers"].abs() < TOLERANCE).all()


def test_scenario_b_removes_exactly_the_attrited_customers(decomposition):
    portfolio = decomposition[(decomposition["grain"] == "portfolio")
                              & (decomposition["method"] == "linear")].set_index("scenario")
    assert portfolio.loc["A", "customers_q1"] == 10127
    assert portfolio.loc["B", "customers_q1"] == 10127
    assert portfolio.loc["B", "customers_q4"] == 8500


def test_low_n_flag_matches_threshold(decomposition):
    cells = decomposition[decomposition["grain"] == "tier_x_tenure"]
    assert (cells["is_low_n"] == (cells["customers_q1"] < 50)).all()
    # every Platinum cell is below the threshold
    assert cells.loc[cells["card_tier"] == "Platinum", "is_low_n"].all()


def test_fallback_is_used_only_where_a_factor_is_zero(decomposition):
    fallback = decomposition[decomposition["decomposition_method"] == "sequential_fallback"]
    # the only real zero-factor cells: attrited customers in scenario B have no Q4 book
    assert len(fallback) > 0
    assert (fallback["customers_q4"] == 0).all()
    assert set(fallback["attrition_flag"]) == {"Attrited Customer"}
    assert set(fallback["scenario"]) == {"B"}


def test_active_flag_does_not_depend_on_the_quarterly_assumption(pipeline_db):
    distinct_counts = pipeline_db.execute("""
        select count(distinct active_q4), count(distinct active_q1)
        from mart_cell_period
        where grain = 'portfolio' and scenario = 'A'
    """).fetchone()
    assert distinct_counts == (1, 1)


def test_segment_shares_add_to_one(pipeline_db):
    rows = pipeline_db.execute("""
        select sum(share_of_portfolio_change), sum(share_of_spend_q1)
        from mart_segment_contribution
        group by method, scenario, grain
    """).fetchall()
    for share_of_change, share_of_spend in rows:
        assert share_of_change == pytest.approx(1.0, abs=1e-9)
        assert share_of_spend == pytest.approx(1.0, abs=1e-9)


def test_fact_table_grain(pipeline_db):
    rows, distinct_rows = pipeline_db.execute("""
        select count(*), count(distinct (scenario_key, customer_id, quarter))
        from pbi_fact_customer_quarter
    """).fetchone()
    assert rows == distinct_rows
    # scenario A: 10,127 x 2. Scenario B: 10,127 in Q1 and 8,500 in Q4.
    assert rows == 10127 * 2 + 10127 + 8500
