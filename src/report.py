"""Write docs/results.md and outputs/headline_numbers.json from the SQL marts.

docs/results.md holds every table the write-ups refer to.
outputs/headline_numbers.json is the place the memo and README take their numbers
from. src/check_docs.py enforces that.
"""
from __future__ import annotations

import json

import duckdb
import pandas as pd

from src.decomposition import sequential_effects, shapley_effects
from src.mdutil import fmt_int, fmt_money, fmt_money_m, fmt_num, fmt_pct, md_table
from src.paths import DB_PATH, DOCS_DIR, OUTPUTS_DIR

BASE = "linear"
METHOD_LABELS = {
    "linear": "Linear trend (base case)",
    "early_step": "Early step: Q2 = Q3 = Q1",
    "late_step": "Late step: Q2 = Q3 = Q4",
}
SCENARIO_LABELS = {"A": "A. As observed", "B": "B. Q4 exit run-rate"}
FACTOR_COLUMNS = {
    "Customers on book": "effect_customers",
    "Active rate": "effect_active_rate",
    "Transactions per active": "effect_txns_per_active",
    "Average ticket": "effect_avg_ticket",
}
TIER_ORDER = ["Blue", "Silver", "Gold", "Platinum"]
TENURE_ORDER = ["13-24", "25-36", "37-48", "49+"]
LOW_N_TEXT = "low n, not interpreted"
SMALL_TIER_NOTE = {"Gold": "small tier (116 customers)", "Platinum": "tiny tier (20 customers)"}


def load() -> dict[str, pd.DataFrame]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = {
            name: con.execute(f"select * from {name}").df()
            for name in ("mart_decomposition", "mart_segment_contribution",
                         "mart_mix_reconciliation")
        }
        tables["q4_below_one_txn"] = con.execute("""
            select count(*) as n from int_customer_quarters
            where method = 'linear' and quarter = 'Q4' and txn_count > 0 and txn_count < 1
        """).df()
        tables["inconsistent_rows"] = con.execute("""
            select count(*) as n from stg_customers
            where ct_ratio_q4_q1 = 0 and amt_ratio_q4_q1 > 0
        """).df()
    finally:
        con.close()
    tables["sql_vs_python"] = pd.read_csv(OUTPUTS_DIR / "sql_vs_python_check.csv")
    return tables


def cell(decomp: pd.DataFrame, scenario: str, grain: str = "portfolio", method: str = BASE,
         **labels: str) -> pd.Series:
    mask = (decomp["method"] == method) & (decomp["scenario"] == scenario) \
        & (decomp["grain"] == grain)
    for column, value in labels.items():
        mask &= decomp[column] == value
    rows = decomp[mask]
    if len(rows) != 1:
        raise ValueError(f"Expected one row for {scenario}/{grain}/{labels}, got {len(rows)}")
    return rows.iloc[0]


def factors(row: pd.Series, quarter: str) -> tuple[float, float, float, float]:
    return (float(row[f"customers_{quarter}"]), row[f"active_rate_{quarter}"],
            row[f"txns_per_active_{quarter}"], row[f"avg_ticket_{quarter}"])


# --------------------------------------------------------------------------------------
# Headline numbers
# --------------------------------------------------------------------------------------

def headline_numbers(t: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Every number the write-ups may quote, already formatted."""
    d, contrib = t["mart_decomposition"], t["mart_segment_contribution"]
    a, b = cell(d, "A"), cell(d, "B")
    facts: dict[str, str] = {}

    # Book
    facts["customers_total"] = fmt_int(a["customers_q1"])
    facts["customers_existing"] = fmt_int(b["customers_q4"])
    facts["customers_attrited"] = fmt_int(a["customers_q1"] - b["customers_q4"])
    facts["attrition_rate"] = fmt_pct(1 - b["customers_q4"] / a["customers_q1"])

    # Scenario A, as observed
    facts["a_spend_q1"] = fmt_money_m(a["spend_q1"])
    facts["a_spend_q4"] = fmt_money_m(a["spend_q4"])
    facts["a_delta_spend"] = fmt_money_m(a["delta_spend"])
    facts["a_pct_change"] = fmt_pct(a["pct_change"])
    facts["a_effect_txns_per_active"] = fmt_money_m(a["effect_txns_per_active"])
    facts["a_effect_avg_ticket"] = fmt_money_m(a["effect_avg_ticket"])
    facts["a_effect_active_rate"] = fmt_money(a["effect_active_rate"])
    facts["a_effect_customers"] = fmt_money(a["effect_customers"])
    facts["a_share_txns_per_active"] = fmt_pct(a["effect_txns_per_active"] / a["delta_spend"])
    facts["a_share_avg_ticket"] = fmt_pct(a["effect_avg_ticket"] / a["delta_spend"])
    facts["a_share_active_rate"] = fmt_pct(a["effect_active_rate"] / a["delta_spend"])
    facts["a_txns_per_active_q1"] = fmt_num(a["txns_per_active_q1"], 1)
    facts["a_txns_per_active_q4"] = fmt_num(a["txns_per_active_q4"], 1)
    facts["a_txns_per_active_pct_change"] = fmt_pct(
        a["txns_per_active_q4"] / a["txns_per_active_q1"] - 1)
    facts["a_avg_ticket_q1"] = fmt_money(a["avg_ticket_q1"], 2)
    facts["a_avg_ticket_q4"] = fmt_money(a["avg_ticket_q4"], 2)
    facts["a_avg_ticket_pct_change"] = fmt_pct(a["avg_ticket_q4"] / a["avg_ticket_q1"] - 1)
    facts["a_active_rate_q1"] = fmt_pct(a["active_rate_q1"], 2)
    facts["a_active_rate_q4"] = fmt_pct(a["active_rate_q4"], 2)
    facts["a_inactive_customers_q4"] = fmt_int(a["customers_q4"] - a["active_q4"])
    facts["a_spend_per_customer_q1"] = fmt_money(a["spend_q1"] / a["customers_q1"])
    facts["a_spend_per_customer_q4"] = fmt_money(a["spend_q4"] / a["customers_q4"])

    # Scenario B, Q4 exit run-rate
    facts["b_spend_q4"] = fmt_money_m(b["spend_q4"])
    facts["b_delta_spend"] = fmt_money_m(b["delta_spend"])
    facts["b_pct_change"] = fmt_pct(b["pct_change"])
    facts["b_effect_customers"] = fmt_money_m(b["effect_customers"])
    facts["b_effect_txns_per_active"] = fmt_money_m(b["effect_txns_per_active"])
    facts["b_effect_avg_ticket"] = fmt_money_m(b["effect_avg_ticket"])
    facts["b_share_customers"] = fmt_pct(b["effect_customers"] / b["delta_spend"])
    facts["b_share_txns_per_active"] = fmt_pct(b["effect_txns_per_active"] / b["delta_spend"])
    facts["b_share_avg_ticket"] = fmt_pct(b["effect_avg_ticket"] / b["delta_spend"])
    facts["b_txns_per_active_q4"] = fmt_num(b["txns_per_active_q4"], 1)
    facts["b_avg_ticket_q4"] = fmt_money(b["avg_ticket_q4"], 2)
    facts["b_minus_a_pct_change_pts"] = fmt_num((b["pct_change"] - a["pct_change"]) * 100, 1)

    # Segments, scenario A
    def contribution(scenario: str, grain: str, **labels: str) -> pd.Series:
        return cell(contrib, scenario, grain, **labels)

    blue = contribution("A", "tier", card_tier="Blue")
    facts["blue_customers"] = fmt_int(blue["customers_q1"])
    facts["blue_share_of_customers"] = fmt_pct(blue["share_of_customers_q1"])
    facts["blue_share_of_spend_q1"] = fmt_pct(blue["share_of_spend_q1"])
    facts["blue_share_of_change"] = fmt_pct(blue["share_of_portfolio_change"])
    for tier in TIER_ORDER:
        row = contribution("A", "tier", card_tier=tier)
        facts[f"{tier.lower()}_pct_change"] = fmt_pct(row["pct_change"])
        facts[f"{tier.lower()}_tier_customers"] = fmt_int(row["customers_q1"])
    for band in TENURE_ORDER:
        row = contribution("A", "tenure", tenure_band=band)
        facts[f"tenure_{band}_pct_change"] = fmt_pct(row["pct_change"])

    cells_a = contrib[(contrib["method"] == BASE) & (contrib["scenario"] == "A")
                      & (contrib["grain"] == "tier_x_tenure")]
    ok = cells_a[~cells_a["is_low_n"]]
    facts["cells_total"] = fmt_int(len(cells_a))
    facts["cells_interpretable"] = fmt_int(len(ok))
    facts["cells_low_n"] = fmt_int(len(cells_a) - len(ok))
    facts["cells_pct_change_mildest"] = fmt_pct(ok["pct_change"].max())
    facts["cells_pct_change_steepest"] = fmt_pct(ok["pct_change"].min())
    facts["cells_over_index_min"] = fmt_num(ok["over_index"].min(), 2)
    facts["cells_over_index_max"] = fmt_num(ok["over_index"].max(), 2)
    facts["cells_with_frequency_as_driver"] = fmt_int(
        (ok["dominant_driver"] == "Transactions per active").sum())
    core = ok[(ok["card_tier"] == "Blue") & (ok["tenure_band"].isin(["25-36", "37-48"]))]
    facts["blue_25_48_customers"] = fmt_int(core["customers_q1"].sum())
    facts["blue_25_48_share_of_customers"] = fmt_pct(core["share_of_customers_q1"].sum())
    facts["blue_25_48_share_of_spend_q1"] = fmt_pct(core["share_of_spend_q1"].sum())
    facts["blue_25_48_share_of_change"] = fmt_pct(core["share_of_portfolio_change"].sum())
    facts["blue_25_48_delta_spend"] = fmt_money_m(core["delta_spend"].sum())
    top = ok.sort_values("contribution_rank").iloc[0]
    facts["top_cell"] = top["segment"]
    facts["top_cell_share_of_change"] = fmt_pct(top["share_of_portfolio_change"])
    facts["top_cell_share_of_spend_q1"] = fmt_pct(top["share_of_spend_q1"])

    # Attrition lens
    att_a = cell(d, "A", "attrition", attrition_flag="Attrited Customer")
    ext_a = cell(d, "A", "attrition", attrition_flag="Existing Customer")
    att_c = contribution("A", "attrition", attrition_flag="Attrited Customer")
    facts["attrited_share_of_spend_q1"] = fmt_pct(att_c["share_of_spend_q1"])
    facts["attrited_share_of_change_a"] = fmt_pct(att_c["share_of_portfolio_change"])
    facts["attrited_spend_q1"] = fmt_money_m(att_a["spend_q1"])
    facts["attrited_spend_q4"] = fmt_money_m(att_a["spend_q4"])
    facts["attrited_share_of_spend_q4"] = fmt_pct(att_a["spend_q4"] / a["spend_q4"])
    facts["attrited_pct_change"] = fmt_pct(att_a["pct_change"])
    facts["existing_pct_change"] = fmt_pct(ext_a["pct_change"])
    facts["existing_delta_spend"] = fmt_money_m(ext_a["delta_spend"])
    facts["attrited_spend_per_customer_q1"] = fmt_money(att_a["spend_q1"] / att_a["customers_q1"])
    facts["existing_spend_per_customer_q1"] = fmt_money(ext_a["spend_q1"] / ext_a["customers_q1"])
    facts["attrited_vs_existing_spend_per_customer_q1"] = fmt_pct(
        (att_a["spend_q1"] / att_a["customers_q1"]) / (ext_a["spend_q1"] / ext_a["customers_q1"]) - 1)
    for label, row in (("attrited", att_a), ("existing", ext_a)):
        t1, t4 = row["txns_q1"] / row["customers_q1"], row["txns_q4"] / row["customers_q4"]
        facts[f"{label}_txns_per_customer_q1"] = fmt_num(t1, 1)
        facts[f"{label}_txns_per_customer_q4"] = fmt_num(t4, 1)
        facts[f"{label}_txns_per_customer_pct_change"] = fmt_pct(t4 / t1 - 1)
        facts[f"{label}_avg_ticket_q1"] = fmt_money(row["avg_ticket_q1"], 2)
        facts[f"{label}_avg_ticket_q4"] = fmt_money(row["avg_ticket_q4"], 2)
        facts[f"{label}_avg_ticket_pct_change"] = fmt_pct(
            row["avg_ticket_q4"] / row["avg_ticket_q1"] - 1)

    # Sensitivity to the quarterly assumption
    port = d[d["grain"] == "portfolio"]
    for scenario, tag in (("A", "a"), ("B", "b")):
        rows = port[port["scenario"] == scenario]
        facts[f"sens_{tag}_pct_change_low"] = fmt_pct(rows["pct_change"].max())
        facts[f"sens_{tag}_pct_change_high"] = fmt_pct(rows["pct_change"].min())
        share = rows["effect_txns_per_active"] / rows["delta_spend"]
        facts[f"sens_{tag}_share_txns_per_active_low"] = fmt_pct(share.min())
        facts[f"sens_{tag}_share_txns_per_active_high"] = fmt_pct(share.max())
    rows_b = port[port["scenario"] == "B"]
    share_n = rows_b["effect_customers"] / rows_b["delta_spend"]
    facts["sens_b_share_customers_low"] = fmt_pct(share_n.min())
    facts["sens_b_share_customers_high"] = fmt_pct(share_n.max())
    ok_all = contrib[(contrib["grain"] == "tier_x_tenure") & ~contrib["is_low_n"]]
    drivers = ok_all.groupby(["scenario", "segment"])["dominant_driver"].nunique()
    ranks = ok_all.groupby(["scenario", "segment"])["contribution_rank"].nunique()
    facts["sens_cells_driver_changes"] = fmt_int((drivers > 1).sum())
    facts["sens_cells_rank_changes"] = fmt_int((ranks > 1).sum())

    # LMDI versus sequential substitution
    facts["a_seq_share_txns_per_active"] = fmt_pct(a["seq_txns_per_active"] / a["delta_spend"])
    facts["a_seq_share_avg_ticket"] = fmt_pct(a["seq_avg_ticket"] / a["delta_spend"])
    facts["b_seq_share_customers"] = fmt_pct(b["seq_customers"] / b["delta_spend"])
    facts["b_seq_share_txns_per_active"] = fmt_pct(b["seq_txns_per_active"] / b["delta_spend"])

    # Data handling and validation
    facts["low_n_threshold"] = "50"
    facts["inconsistent_rows"] = fmt_int(t["inconsistent_rows"]["n"].iloc[0])
    facts["q4_customers_below_one_txn"] = fmt_int(t["q4_below_one_txn"]["n"].iloc[0])
    facts["cells_decomposed"] = fmt_int(len(d))
    facts["sql_vs_python_max_abs_diff"] = f"{t['sql_vs_python']['max_abs_diff'].max():.1e}"
    facts["max_abs_residual"] = f"{d['residual'].abs().max():.1e}"
    mix = t["mart_mix_reconciliation"]
    facts["mix_gap_max_abs"] = fmt_money(mix[mix["method"] == BASE]["mix_gap"].abs().max())
    return facts


# --------------------------------------------------------------------------------------
# Tables for docs/results.md
# --------------------------------------------------------------------------------------

def kpi_table(row: pd.Series) -> str:
    spc1 = row["spend_q1"] / row["customers_q1"]
    spc4 = row["spend_q4"] / row["customers_q4"]
    lines = [
        ("Spend", fmt_money_m(row["spend_q1"]), fmt_money_m(row["spend_q4"]),
         fmt_pct(row["pct_change"], signed=True)),
        ("Customers on book", fmt_int(row["customers_q1"]), fmt_int(row["customers_q4"]),
         fmt_pct(row["customers_q4"] / row["customers_q1"] - 1, signed=True)),
        ("Active rate", fmt_pct(row["active_rate_q1"], 2), fmt_pct(row["active_rate_q4"], 2),
         fmt_pct(row["active_rate_q4"] / row["active_rate_q1"] - 1, 2, signed=True)),
        ("Transactions per active customer", fmt_num(row["txns_per_active_q1"]),
         fmt_num(row["txns_per_active_q4"]),
         fmt_pct(row["txns_per_active_q4"] / row["txns_per_active_q1"] - 1, signed=True)),
        ("Average ticket", fmt_money(row["avg_ticket_q1"], 2), fmt_money(row["avg_ticket_q4"], 2),
         fmt_pct(row["avg_ticket_q4"] / row["avg_ticket_q1"] - 1, signed=True)),
        ("Spend per customer on book", fmt_money(spc1), fmt_money(spc4),
         fmt_pct(spc4 / spc1 - 1, signed=True)),
    ]
    return md_table(pd.DataFrame(lines, columns=["Metric", "Q1", "Q4", "Change"]),
                    align_right=["Q1", "Q4", "Change"])


def bridge_table(row: pd.Series) -> str:
    lines = [("Q1 spend", fmt_money_m(row["spend_q1"]), "", "")]
    for label, column in FACTOR_COLUMNS.items():
        lines.append((label, fmt_money(row[column]),
                      fmt_pct(row[column] / row["delta_spend"]),
                      fmt_pct(row[column] / row["spend_q1"], signed=True)))
    lines.append(("Q4 spend", fmt_money_m(row["spend_q4"]), "", ""))
    lines.append(("Total change", fmt_money(row["delta_spend"]), "100.0%",
                  fmt_pct(row["pct_change"], signed=True)))
    return md_table(pd.DataFrame(lines, columns=["Step", "Amount", "Share of change",
                                                 "As % of Q1 spend"]),
                    align_right=["Amount", "Share of change", "As % of Q1 spend"])


def segment_table(contrib: pd.DataFrame, scenario: str, grain: str) -> str:
    rows = contrib[(contrib["method"] == BASE) & (contrib["scenario"] == scenario)
                   & (contrib["grain"] == grain)].sort_values("contribution_rank")
    lines = []
    for r in rows.itertuples():
        if grain == "tier_x_tenure":
            note = LOW_N_TEXT if r.is_low_n else "ok"
        elif grain == "tier":
            note = SMALL_TIER_NOTE.get(r.card_tier, "ok")
        else:
            note = "ok"
        lines.append((
            r.segment, fmt_int(r.customers_q1), fmt_money_m(r.spend_q1),
            fmt_pct(r.pct_change, signed=True), fmt_money(r.delta_spend),
            fmt_pct(r.share_of_spend_q1), fmt_pct(r.share_of_portfolio_change),
            fmt_num(r.over_index), r.dominant_driver, note,
        ))
    columns = ["Segment", "Customers (Q1)", "Q1 spend", "% change", "Spend change",
               "Share of Q1 spend", "Share of portfolio change", "Over-index",
               "Dominant driver", "Sample"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:8])


def segment_effects_table(contrib: pd.DataFrame, scenario: str, grain: str) -> str:
    rows = contrib[(contrib["method"] == BASE) & (contrib["scenario"] == scenario)
                   & (contrib["grain"] == grain)].sort_values("contribution_rank")
    lines = []
    for r in rows.itertuples():
        lines.append((
            r.segment, fmt_money(r.delta_spend), fmt_money(r.effect_customers),
            fmt_money(r.effect_active_rate), fmt_money(r.effect_txns_per_active),
            fmt_money(r.effect_avg_ticket),
            "sequential fallback" if r.decomposition_method != "lmdi" else "LMDI",
            LOW_N_TEXT if (grain == "tier_x_tenure" and r.is_low_n) else "",
        ))
    columns = ["Segment", "Spend change", "Customers on book", "Active rate",
               "Transactions per active", "Average ticket", "Method", "Flag"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:6])


def sensitivity_table(d: pd.DataFrame) -> str:
    lines = []
    for scenario in ("A", "B"):
        for method in METHOD_LABELS:
            r = cell(d, scenario, method=method)
            lines.append((
                SCENARIO_LABELS[scenario], METHOD_LABELS[method],
                fmt_money_m(r["spend_q1"]), fmt_money_m(r["spend_q4"]),
                fmt_pct(r["pct_change"], signed=True),
                fmt_pct(r["effect_customers"] / r["delta_spend"]),
                fmt_pct(r["effect_active_rate"] / r["delta_spend"]),
                fmt_pct(r["effect_txns_per_active"] / r["delta_spend"]),
                fmt_pct(r["effect_avg_ticket"] / r["delta_spend"]),
                r["dominant_driver"],
            ))
    columns = ["Scenario", "Quarterly assumption", "Q1 spend", "Q4 spend", "% change",
               "Customers", "Active rate", "Txns per active", "Avg ticket", "Dominant driver"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[2:9])


def sensitivity_cells_table(contrib: pd.DataFrame) -> str:
    ok = contrib[(contrib["grain"] == "tier_x_tenure") & ~contrib["is_low_n"]
                 & (contrib["scenario"] == "A")]
    lines = []
    base_order = ok[ok["method"] == BASE].sort_values("contribution_rank")["segment"]
    for segment in base_order:
        rows = ok[ok["segment"] == segment].set_index("method")
        lines.append((
            segment,
            *(fmt_pct(rows.loc[m, "pct_change"], signed=True) for m in METHOD_LABELS),
            *(fmt_pct(rows.loc[m, "share_of_portfolio_change"]) for m in METHOD_LABELS),
            "yes" if rows["contribution_rank"].nunique() == 1 else "no",
            "yes" if rows["dominant_driver"].nunique() == 1 else "no",
        ))
    columns = ["Cell", "% change, linear", "% change, early step", "% change, late step",
               "Share of change, linear", "Share, early step", "Share, late step",
               "Same rank", "Same driver"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:7])


def method_comparison_table(row: pd.Series) -> str:
    f0, f1 = factors(row, "q1"), factors(row, "q4")
    forward = sequential_effects(f0, f1, order=[0, 1, 2, 3])
    reverse = sequential_effects(f0, f1, order=[3, 2, 1, 0])
    shapley = shapley_effects(f0, f1)
    lines = []
    for k, (label, column) in enumerate(FACTOR_COLUMNS.items()):
        lines.append((
            label, fmt_money(row[column]), fmt_money(forward[k]), fmt_money(reverse[k]),
            fmt_money(shapley[k]), fmt_money(forward[k] - row[column]),
        ))
    lines.append(("Total", fmt_money(row["delta_spend"]), fmt_money(sum(forward)),
                  fmt_money(sum(reverse)), fmt_money(sum(shapley)), ""))
    columns = ["Factor", "LMDI", "Sequential, customers first", "Sequential, ticket first",
               "Average of all 24 orders", "Sequential (customers first) minus LMDI"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:])


def mix_table(mix: pd.DataFrame, scenario: str) -> str:
    rows = mix[(mix["method"] == BASE) & (mix["scenario"] == scenario)].sort_values("factor_order")
    lines = [(r.factor, fmt_money(r.portfolio_level_effect), fmt_money(r.sum_of_cell_effects),
              fmt_money(r.mix_gap)) for r in rows.itertuples()]
    columns = ["Factor", "Portfolio-level effect", "Sum of tier x tenure cell effects", "Gap (mix)"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:])


def attrition_table(d: pd.DataFrame) -> str:
    lines = []
    total = cell(d, "A")
    for flag in ("Existing Customer", "Attrited Customer"):
        r = cell(d, "A", "attrition", attrition_flag=flag)
        t1, t4 = r["txns_q1"] / r["customers_q1"], r["txns_q4"] / r["customers_q4"]
        lines.append((
            flag, fmt_int(r["customers_q1"]),
            fmt_pct(r["customers_q1"] / total["customers_q1"]),
            fmt_pct(r["spend_q1"] / total["spend_q1"]),
            fmt_money(r["spend_q1"] / r["customers_q1"]),
            fmt_money(r["spend_q4"] / r["customers_q4"]),
            fmt_pct(r["pct_change"], signed=True),
            f"{fmt_num(t1, 1)} to {fmt_num(t4, 1)} ({fmt_pct(t4 / t1 - 1, signed=True)})",
            f"{fmt_money(r['avg_ticket_q1'], 2)} to {fmt_money(r['avg_ticket_q4'], 2)} "
            f"({fmt_pct(r['avg_ticket_q4'] / r['avg_ticket_q1'] - 1, signed=True)})",
        ))
    columns = ["Group", "Customers", "Share of customers", "Share of Q1 spend",
               "Q1 spend per customer", "Q4 spend per customer", "Spend change",
               "Transactions per customer, Q1 to Q4", "Average ticket, Q1 to Q4"]
    return md_table(pd.DataFrame(lines, columns=columns), align_right=columns[1:7])


def build_results(t: dict[str, pd.DataFrame], facts: dict[str, str]) -> str:
    d, contrib, mix = (t["mart_decomposition"], t["mart_segment_contribution"],
                       t["mart_mix_reconciliation"])
    out: list[str] = []
    add = out.append

    add("# Results\n")
    add("Generated by `src/report.py` from the DuckDB marts. Do not edit by hand, rerun "
        "`run_all`. Base case is the linear quarterly assumption unless a table says "
        "otherwise. All dollar values are derived estimates, see `ASSUMPTIONS.md`.\n")

    for scenario in ("A", "B"):
        row = cell(d, scenario)
        add(f"## Scenario {SCENARIO_LABELS[scenario]}\n")
        add("### Portfolio KPIs\n")
        add(kpi_table(row))
        add("\n### Spend bridge (additive LMDI)\n")
        add(bridge_table(row))
        add("\nA share of change above 100% means the factor alone would have caused a "
            "bigger move than the one observed, and another factor pulled the other way.\n")
        add("### By card tier\n")
        add(segment_table(contrib, scenario, "tier"))
        add("")
        add(segment_effects_table(contrib, scenario, "tier"))
        add("\nGold (116 customers) and Platinum (20 customers) are tiny. Their rows are "
            "shown for completeness and are not used for any conclusion.\n")
        add("### By tenure band\n")
        add(segment_table(contrib, scenario, "tenure"))
        add("")
        add(segment_effects_table(contrib, scenario, "tenure"))
        add("\n### By tier x tenure cell\n")
        add(segment_table(contrib, scenario, "tier_x_tenure"))
        add("")
        add(segment_effects_table(contrib, scenario, "tier_x_tenure"))
        add(f"\nCells with fewer than {facts['low_n_threshold']} customers on the Q1 book are "
            f"flagged \"{LOW_N_TEXT}\". Platinum / 49+ has no customers and does not appear. "
            "Over-index is share of portfolio change divided by share of Q1 spend.\n")

    add("## Attrition lens\n")
    add("Scenario A values, so attrited customers still have Q4 numbers.\n")
    add(attrition_table(d))
    add("\n### Cohort view of scenario B\n")
    add("Scenario B can also be read by cohort instead of by factor. The two cohort "
        "rows add up to the scenario B change exactly.\n")
    add(segment_effects_table(contrib, "B", "attrition"))
    add(f"\nThe attrited cohort has no Q4 customers, so LMDI is undefined for it and the "
        f"cell uses the sequential fallback. The whole change is a customers effect: their "
        f"Q1 spend of {facts['attrited_spend_q1']} leaves the book.\n")
    add(f"Note the difference from the portfolio bridge for scenario B. The portfolio-level "
        f"customers effect is {facts['b_effect_customers']}, which is larger than the "
        f"{facts['attrited_spend_q1']} the attrited customers actually spent in Q1. The "
        f"portfolio identity prices every lost customer at the portfolio average, and "
        f"attrited customers spent {facts['attrited_vs_existing_spend_per_customer_q1'].lstrip('-')} "
        f"less per head than existing customers. The offset shows up as smaller negative "
        f"frequency and ticket effects, because the customers who remain are heavier "
        f"spenders on average. Both views add up to the same total.\n")

    add("## Sensitivity to the quarterly assumption\n")
    add(sensitivity_table(d))
    add("\nFactor columns are shares of the spend change.\n")
    add("### Interpretable tier x tenure cells, scenario A\n")
    add(sensitivity_cells_table(contrib))
    add(f"\nAcross both scenarios, {facts['sens_cells_driver_changes']} interpretable cells "
        f"change dominant driver and {facts['sens_cells_rank_changes']} change contribution "
        f"rank when the assumption changes.\n")

    add("## LMDI versus sequential substitution\n")
    for scenario in ("A", "B"):
        add(f"### Scenario {SCENARIO_LABELS[scenario]}\n")
        add(method_comparison_table(cell(d, scenario)))
        add("")
    add("All four methods add up to the same total. They differ in how they share out the "
        "interaction between factors. Sequential substitution values each step at the "
        "levels left by the steps before it, so the answer depends on the order. LMDI uses "
        "one common weight, the log mean of Q1 and Q4 spend, for every factor, so there is "
        "no order to choose. The average over all 24 orders lands close to LMDI, which is "
        "the expected behaviour.\n")

    add("## Portfolio-level effects versus the sum of cell effects\n")
    for scenario in ("A", "B"):
        add(f"### Scenario {SCENARIO_LABELS[scenario]}\n")
        add(mix_table(mix, scenario))
        add("")
    add(f"The gaps add to zero. The largest is {facts['mix_gap_max_abs']}, so mix shifts "
        f"between tier x tenure cells are not a material part of the story.\n")

    add("## Validation\n")
    add(f"- Cells decomposed (3 assumptions x 2 scenarios x 5 grains): {facts['cells_decomposed']}")
    add(f"- Largest absolute gap between the sum of effects and the spend change, in "
        f"dollars: {facts['max_abs_residual']}")
    add(f"- Largest absolute difference between the SQL and Python implementations across "
        f"all compared columns: {facts['sql_vs_python_max_abs_diff']} (tolerance 1e-6)\n")

    add("## Headline numbers\n")
    add("These are the numbers the memo and README quote. "
        "`src/check_docs.py` fails the build if a quoted number is not in this list.\n")
    add(md_table(pd.DataFrame({"Key": [f"`{k}`" for k in facts], "Value": list(facts.values())}),
                 align_right=["Value"]))
    return "\n".join(out) + "\n"


def main() -> None:
    tables = load()
    facts = headline_numbers(tables)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "headline_numbers.json").write_text(
        json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    (DOCS_DIR / "results.md").write_text(build_results(tables, facts), encoding="utf-8",
                                         newline="\n")
    print(f"Wrote {DOCS_DIR / 'results.md'} and {OUTPUTS_DIR / 'headline_numbers.json'}")


if __name__ == "__main__":
    main()
