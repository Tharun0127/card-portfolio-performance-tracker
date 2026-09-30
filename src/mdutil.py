"""Small helpers for writing markdown and formatting numbers the same way everywhere."""
from __future__ import annotations

import math

import pandas as pd


def md_table(df: pd.DataFrame, align_right: list[str] | None = None) -> str:
    """Render a DataFrame as a GitHub markdown table. Values must already be strings."""
    align_right = align_right or []
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    rule = "|" + "|".join("---:" if c in align_right else "---" for c in df.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, rule, *rows])


def fmt_int(x: float) -> str:
    return f"{int(round(x)):,}"


def fmt_money(x: float, decimals: int = 0) -> str:
    """$1,234 or -$1,234."""
    x = round(x, decimals)
    sign = "-" if x < 0 else ""  # rounding first avoids "-$0"
    return f"{sign}${abs(x):,.{decimals}f}"


def fmt_money_m(x: float, decimals: int = 2) -> str:
    """Dollars in millions: $12.74M or -$3.18M."""
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x) / 1e6:,.{decimals}f}M"


def fmt_pct(x: float, decimals: int = 1, signed: bool = False) -> str:
    """0.1234 -> 12.3%. NaN -> n/a."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    value = round(x * 100, decimals)
    if value == 0:
        value = 0.0  # avoid "-0.0%"
    return f"{value:+.{decimals}f}%" if signed else f"{value:.{decimals}f}%"


def fmt_num(x: float, decimals: int = 2) -> str:
    return f"{x:,.{decimals}f}"
