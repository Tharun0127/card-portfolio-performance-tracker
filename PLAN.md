# Plan: Card Portfolio Performance Tracker

## Goal

Answer one business question with a method that can be defended line by line:

> Q4 card spend differs from Q1. How much of the change came from customers on book,
> active rate, transactions per active customer, and average transaction size? Which
> card tiers and tenure bands drive it, and what should the portfolio team do?

## What I found in the raw data before planning

- 10,127 customers, 23 columns, no nulls, no duplicate `CLIENTNUM`.
- 8,500 existing and 1,627 attrited customers.
- Card tiers are very uneven: Blue 9,436, Silver 555, Gold 116, Platinum 20.
- The file has 12-month totals and Q4/Q1 ratios, not quarterly levels. Quarterly
  values have to be derived under an assumption.
- Every customer has at least 10 transactions in the year. Only 7 customers have a
  Q4/Q1 count ratio of zero. So "active rate" will be close to 100% in both quarters
  and cannot explain much. I will report that plainly instead of forcing a story.
- 2 of those 7 customers have a count ratio of zero but an amount ratio above zero.
  That is internally inconsistent and needs an explicit rule.
- `Months_on_book` has a spike at exactly 36 months (2,463 customers), which looks
  like imputation by the data provider. It goes in the profile and the limitations.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Base-case quarterly derivation | Linear trend: `Q1 = total / (2 * (1 + r))`, `Q4 = r * Q1` | Simple, easy to explain, and the only shape that needs no extra parameter. |
| Sensitivity | Two alternatives that bracket the base case: "early step" (Q2 = Q3 = Q1) and "late step" (Q2 = Q3 = Q4) | One would be enough. The second costs nothing and shows both directions. |
| Active | A customer is active in a quarter if the quarterly transaction count is above zero. In Q4 that is `Total_Ct_Chng_Q4_Q1 > 0`. | This flag comes straight from the data and does not depend on the quarterly assumption. |
| Inconsistent rows | If the Q4 count is zero, Q4 spend is set to zero | No transactions means no spend. Affects 2 customers. |
| Scenario A | Same customers on book in Q1 and Q4 | As observed. |
| Scenario B | Attrited customers are off book at Q4 end, so their Q4 spend and counts are removed | Q4 exit run-rate. |
| Segments | `Card_Category` x tenure band (13-24, 25-36, 37-48, 49+) | Project scope. |
| Low n | Any cell under 50 customers is flagged "low n, not interpreted" | Project scope. |
| Decomposition | Additive LMDI, with sequential substitution as the fallback for cells with a zero factor and as a cross-check | LMDI is exact and does not depend on factor order. |
| SQL engine | DuckDB, files in `sql/staging`, `sql/intermediate`, `sql/marts` | Project scope. |
| Python version | 3.11 in a local `.venv` | Project scope. |

## Steps (one git commit each)

1. **Scaffold.** `PLAN.md`, `.gitignore`, pinned `requirements.txt`, data download script.
2. **Profile.** `src/profile_data.py` writes `docs/data_profile.md`: nulls, "Unknown"
   categories, distributions, segment sizes, low-n cells.
3. **SQL pipeline.** Staging (clean, drop the two `Naive_Bayes_Classifier` columns),
   intermediate (quarterly derivation for each assumption, segments, scenarios),
   marts (segment aggregates, LMDI decomposition, segment contribution).
4. **Python decomposition and validation.** Pure functions in `src/decomposition.py`,
   an independent pandas rebuild from the raw CSV, and an assertion that SQL and Python
   agree within 1e-6.
5. **Tests.** pytest: effects sum to the total, zero-change case, single-factor-change
   case, zero-factor fallback, SQL on synthetic inputs, SQL versus Python on real data.
6. **Results and sensitivity.** `docs/results.md` with every table used in the write-ups,
   `outputs/headline_numbers.json` as the single source for quoted numbers,
   `ASSUMPTIONS.md` with the derivation and the sensitivity check.
7. **Power BI.** Star schema CSVs, `measures.dax`, `POWERBI_BUILD_GUIDE.md`.
8. **Plotly dashboard.** `docs/index.html`, self-contained, 4 pages, scenario switch.
9. **Write-ups.** `docs/memo.md` and `README.md`, plus a script that checks every number
   quoted in them against the pipeline outputs.
10. **Rebuild from scratch.** Delete build outputs, run `run_all`, confirm tests pass,
    summarise findings and anything not verified.

## Repository layout

```
data/raw/            raw Kaggle CSV (git-ignored)
sql/staging/         stg_customers
sql/intermediate/    quarterly derivation, segments, scenarios
sql/marts/           cell aggregates, decomposition, contribution, Power BI tables
src/                 pipeline runner, Python decomposition, profile, report, dashboard
tests/               pytest
outputs/             mart CSVs and headline numbers
powerbi/             star schema CSVs, measures.dax, build guide
docs/                index.html (GitHub Pages), memo, data profile, results
```

## Things I already know I cannot verify here

- Power BI Desktop is not scripted in this build. The DAX and the build guide are
  written carefully and the DAX logic mirrors the SQL, but the report itself has to be
  assembled by hand and checked against `docs/results.md`.
- The dataset is a public teaching dataset. Nothing here says anything about a real
  issuer's portfolio.

## Outcome (added after the build)

All ten steps were completed. Differences from the plan above:

- Python 3.11 was not installed on the build machine, so it was added with
  `py install 3.11`. The Kaggle CLI is installed inside `.venv` from `requirements.txt`.
- The Power BI folder has one table more than the five planned:
  `dim_bridge_step`, a disconnected helper that supplies the waterfall axis. It also
  has `expected_values.csv` for checking the report, and `theme.json`.
- The decomposition runs at a fifth grain, attrition status, which feeds the attrition
  page and is the only place the zero-factor fallback is triggered by real data.
- The final rebuild from an empty folder (no `.venv`, no data, no outputs) reproduced
  every committed output file exactly.
