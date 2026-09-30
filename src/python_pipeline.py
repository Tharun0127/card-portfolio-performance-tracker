"""Independent pandas rebuild of the decomposition, straight from the raw CSV.

Nothing here reads the DuckDB tables. It repeats the quarterly derivation, the
scenarios, the aggregation and the decomposition so that src/validate.py can compare
two separate implementations.
"""
from __future__ import annotations

import math

import pandas as pd

from src.decomposition import decompose, factors_from_totals, lmdi_effects, sequential_effects
from src.paths import RAW_CSV

LOW_N_THRESHOLD = 50

# Q1 = total / (a + b * r). See ASSUMPTIONS.md.
ASSUMPTIONS = {"linear": (2.0, 2.0), "early_step": (3.0, 1.0), "late_step": (1.0, 3.0)}
SCENARIOS = ("A", "B")
GRAINS = {
    "portfolio": [],
    "tier": ["card_tier"],
    "tenure": ["tenure_band"],
    "tier_x_tenure": ["card_tier", "tenure_band"],
    "attrition": ["attrition_flag"],
}
KEYS = ["method", "scenario", "grain", "card_tier", "tenure_band", "attrition_flag"]


def load_customers() -> pd.DataFrame:
    raw = pd.read_csv(RAW_CSV)
    raw = raw.drop(columns=[c for c in raw.columns if c.startswith("Naive_Bayes_Classifier")])
    months = raw["Months_on_book"]
    band = pd.Series("49+", index=raw.index)
    band[months <= 48] = "37-48"
    band[months <= 36] = "25-36"
    band[months <= 24] = "13-24"
    ct_ratio = raw["Total_Ct_Chng_Q4_Q1"].astype(float)
    amt_ratio = raw["Total_Amt_Chng_Q4_Q1"].astype(float).where(ct_ratio != 0, 0.0)
    return pd.DataFrame({
        "customer_id": raw["CLIENTNUM"],
        "card_tier": raw["Card_Category"],
        "tenure_band": band,
        "attrition_flag": raw["Attrition_Flag"],
        "is_attrited": raw["Attrition_Flag"] == "Attrited Customer",
        "total_amt": raw["Total_Trans_Amt"].astype(float),
        "total_ct": raw["Total_Trans_Ct"].astype(float),
        "amt_ratio": amt_ratio,
        "ct_ratio": ct_ratio,
    })


def customer_quarters(customers: pd.DataFrame, method: str) -> pd.DataFrame:
    """Q1 and Q4 spend and transaction counts per customer under one assumption."""
    a, b = ASSUMPTIONS[method]
    out = customers.copy()
    out["spend_q1"] = out["total_amt"] / (a + b * out["amt_ratio"])
    out["txns_q1"] = out["total_ct"] / (a + b * out["ct_ratio"])
    out["spend_q4"] = out["amt_ratio"] * out["spend_q1"]
    out["txns_q4"] = out["ct_ratio"] * out["txns_q1"]
    return out


def cell_totals(rows: pd.DataFrame, scenario: str) -> dict[str, float]:
    """The eight totals a cell needs. math.fsum is an exact floating point sum."""
    q4_rows = rows[~rows["is_attrited"]] if scenario == "B" else rows
    return {
        "customers_q1": len(rows),
        "customers_q4": len(q4_rows),
        "active_q1": int((rows["txns_q1"] > 0).sum()),
        "active_q4": int((q4_rows["txns_q4"] > 0).sum()),
        "txns_q1": math.fsum(rows["txns_q1"]),
        "txns_q4": math.fsum(q4_rows["txns_q4"]),
        "spend_q1": math.fsum(rows["spend_q1"]),
        "spend_q4": math.fsum(q4_rows["spend_q4"]),
    }


def decompose_cell(totals: dict[str, float]) -> dict[str, float | str | None]:
    f0 = factors_from_totals(totals["customers_q1"], totals["active_q1"],
                             totals["txns_q1"], totals["spend_q1"])
    f1 = factors_from_totals(totals["customers_q4"], totals["active_q4"],
                             totals["txns_q4"], totals["spend_q4"])
    used, effects = decompose(f0, f1)
    seq = sequential_effects(f0, f1)
    lmdi = lmdi_effects(f0, f1) if used == "lmdi" else [None] * 4
    names = ("customers", "active_rate", "txns_per_active", "avg_ticket")
    out: dict[str, float | str | None] = {
        "delta_spend": totals["spend_q4"] - totals["spend_q1"],
        "decomposition_method": used,
        "active_rate_q1": f0[1], "active_rate_q4": f1[1],
        "txns_per_active_q1": f0[2], "txns_per_active_q4": f1[2],
        "avg_ticket_q1": f0[3], "avg_ticket_q4": f1[3],
    }
    for name, e, l, s in zip(names, effects, lmdi, seq):
        out[f"effect_{name}"] = e
        out[f"lmdi_{name}"] = l
        out[f"seq_{name}"] = s
    return out


def build_decomposition() -> pd.DataFrame:
    """Same grain and keys as the SQL table mart_decomposition."""
    customers = load_customers()
    records = []
    for method in ASSUMPTIONS:
        quarters = customer_quarters(customers, method)
        for scenario in SCENARIOS:
            for grain, by in GRAINS.items():
                groups = [((), quarters)] if not by else quarters.groupby(by, sort=True)
                for key, rows in groups:
                    labels = dict(zip(by, key if isinstance(key, tuple) else (key,)))
                    totals = cell_totals(rows, scenario)
                    records.append({
                        "method": method,
                        "scenario": scenario,
                        "grain": grain,
                        "card_tier": labels.get("card_tier", "All"),
                        "tenure_band": labels.get("tenure_band", "All"),
                        "attrition_flag": labels.get("attrition_flag", "All"),
                        "is_low_n": totals["customers_q1"] < LOW_N_THRESHOLD,
                        **totals,
                        **decompose_cell(totals),
                    })
    return pd.DataFrame.from_records(records).sort_values(KEYS).reset_index(drop=True)


if __name__ == "__main__":
    print(build_decomposition().head(10).to_string())
