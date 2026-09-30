"""Build docs/index.html: a self-contained Plotly version of the four dashboard pages.

The page embeds plotly.js and the data it needs, so it works offline and on GitHub
Pages with no server. All chart titles are written by the page from the data, so a
title can never disagree with the numbers under it.
"""
from __future__ import annotations

import json

import duckdb
import plotly.offline

from src.paths import DB_PATH, DOCS_DIR, OUTPUTS_DIR, ROOT

TEMPLATE = ROOT / "src" / "dashboard_template.html"
TIERS = ["Blue", "Silver", "Gold", "Platinum"]
TENURES = ["13-24", "25-36", "37-48", "49+"]
SCENARIOS = {"A": "A, as observed", "B": "B, Q4 exit run-rate"}

CELL_FIELDS = [
    "segment", "is_low_n", "decomposition_method", "dominant_driver",
    "customers_q1", "customers_q4", "active_q1", "active_q4",
    "txns_q1", "txns_q4", "spend_q1", "spend_q4",
    "active_rate_q1", "active_rate_q4", "txns_per_active_q1", "txns_per_active_q4",
    "avg_ticket_q1", "avg_ticket_q4", "delta_spend", "pct_change",
    "effect_customers", "effect_active_rate", "effect_txns_per_active", "effect_avg_ticket",
]
CONTRIBUTION_FIELDS = ["share_of_spend_q1", "share_of_portfolio_change", "over_index"]


def clean(value):
    """JSON-friendly values. Floats are rounded so the file is stable across runs."""
    if value is None or value != value:  # None or NaN
        return None
    if isinstance(value, bool):
        return value
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value


def build_payload() -> dict:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        decomp = con.execute(
            "select * from mart_decomposition where method = 'linear'").df()
        contrib = con.execute(
            "select * from mart_segment_contribution where method = 'linear'").df()
    finally:
        con.close()

    keys = ["scenario", "grain", "card_tier", "tenure_band", "attrition_flag"]
    merged = decomp.merge(contrib[keys + CONTRIBUTION_FIELDS], on=keys, how="left")

    cells, attrition = {}, {"A": {}, "B": {}}
    for row in merged.to_dict("records"):
        record = {f: clean(row[f]) for f in CELL_FIELDS + CONTRIBUTION_FIELDS}
        if row["grain"] == "attrition":
            attrition[row["scenario"]][row["attrition_flag"]] = record
        else:
            cells[f"{row['scenario']}|{row['card_tier']}|{row['tenure_band']}"] = record

    facts = json.loads((OUTPUTS_DIR / "headline_numbers.json").read_text(encoding="utf-8"))
    return {
        "scenarios": SCENARIOS,
        "tiers": TIERS,
        "tenures": TENURES,
        "low_n_threshold": int(facts["low_n_threshold"]),
        "cells": cells,
        "attrition": attrition,
        "facts": facts,
    }


def main() -> None:
    payload = json.dumps(build_payload(), separators=(",", ":"), sort_keys=True)
    html = TEMPLATE.read_text(encoding="utf-8")
    # "</" inside a script block would end it early, so escape it in both inserts.
    html = html.replace("/*__DATA__*/", payload.replace("</", "<\\/"))
    html = html.replace("/*__PLOTLY__*/", plotly.offline.get_plotlyjs().replace("</script", "<\\/script"))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
