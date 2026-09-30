# Card Portfolio Performance Tracker

**Question.** Q4 card spend differs from Q1. How much of the change came from customers on book, active rate, transactions per active customer, and average ticket, and which segments drive it?

**Answer.** Spend fell 25.0% ($12.74M to $9.56M). All of it is lower transaction frequency (down 29.8%), partly offset by a 7.0% higher average ticket, and every tier and tenure band declined by about the same amount. Removing attrited customers deepens the fall to 33.3%.

**Recommendation.** Treat it as a portfolio-wide usage problem: aim the recovery at transaction frequency in the Blue core (77.2% of spend), and use falling frequency as the retention trigger, ranked by spend at risk.

![Spend bridge: Q1 to Q4, as observed](docs/img/page2_bridge.png)

The quarterly values above are estimates. The dataset has 12-month totals and Q4/Q1 ratios, not quarterly levels, so Q1 and Q4 are derived under a stated assumption and tested against two alternatives. See [ASSUMPTIONS.md](ASSUMPTIONS.md).

## What is here

| Deliverable | Where |
|---|---|
| Interactive dashboard, 4 pages, no install needed | [docs/index.html](docs/index.html) (serve with GitHub Pages from `/docs`) |
| One-page memo | [docs/memo.md](docs/memo.md) |
| Every result table | [docs/results.md](docs/results.md) |
| Data profile | [docs/data_profile.md](docs/data_profile.md) |
| Assumptions and sensitivity check | [ASSUMPTIONS.md](ASSUMPTIONS.md) |
| Power BI star schema, DAX and build guide | [powerbi/](powerbi/POWERBI_BUILD_GUIDE.md) |
| SQL pipeline (DuckDB) | `sql/staging`, `sql/intermediate`, `sql/marts` |
| Python implementation and pipeline runner | `src/` |
| Tests | `tests/` |
| Interview notes | [INTERVIEW_PREP.md](INTERVIEW_PREP.md) |
| Resume bullets | [RESUME_BULLETS.md](RESUME_BULLETS.md) |
| Build plan | [PLAN.md](PLAN.md) |

More dashboard pages: [KPI overview](docs/img/page1_overview.png), [exit run-rate bridge](docs/img/page2_bridge_exit_run_rate.png), [tier x tenure heatmap](docs/img/page3_heatmap.png), [attrition lens](docs/img/page4_attrition.png).

## Method

**Data.** Kaggle dataset `sakshigoyal7/credit-card-customers` (`BankChurners.csv`), 10,127 customers. The two columns starting with `Naive_Bayes_Classifier` are dropped.

**Identity.**

```
spend = customers on book x active rate x transactions per active x average ticket
```

Each factor is a ratio of two totals, so the identity holds exactly for the portfolio and for every segment.

**Decomposition.** Additive LMDI (logarithmic mean Divisia index). Each factor's effect is the log mean of Q1 and Q4 spend multiplied by the log of the factor's ratio. The four effects add up to the spend change with no residual and do not depend on the order of the factors. A cell with a zero factor falls back to sequential substitution and is flagged. Sequential substitution is also computed everywhere as a cross-check.

**Scenarios.**

- A, as observed: the same customers are on book in Q1 and Q4.
- B, Q4 exit run-rate: customers flagged as attrited are off book at Q4 end.

**Segments.** Card tier x tenure band (13-24, 25-36, 37-48, 49+ months). Cells with fewer than 50 customers are flagged "low n, not interpreted". Platinum (20 customers) and Gold (116 customers) are tiny and are not used for any conclusion.

**Pipeline.**

```
data/raw/BankChurners.csv
  -> sql/staging        stg_customers                 clean, rename, drop leaked columns
  -> sql/intermediate   int_customer_quarters         derive Q1 and Q4 under each assumption
                        int_customer_segments         tier x tenure, cell sizes, low-n flag
                        int_customer_quarter_scenario apply scenarios A and B
  -> sql/marts          mart_cell_quarter, mart_cell_period   aggregate to five grains
                        mart_decomposition (+ _long)          LMDI with sequential fallback
                        mart_segment_contribution             share of the portfolio change
                        mart_mix_reconciliation               portfolio effects vs sum of cells
                        pbi_*                                 Power BI star schema
  -> src/python_pipeline.py   independent pandas rebuild from the raw file
  -> src/validate.py          assert SQL and Python agree within 1e-6
```

## Results

| | A. As observed | B. Q4 exit run-rate |
|---|---:|---:|
| Q1 spend | $12.74M | $12.74M |
| Q4 spend | $9.56M | $8.50M |
| Change | -25.0% | -33.3% |
| Customers on book | $0 | -$1.83M |
| Active rate | -$7,657 | $0 |
| Transactions per active | -$3.92M | -$2.95M |
| Average ticket | $0.75M | $0.54M |
| Total change | -$3.18M | -$4.25M |

- Transactions per active customer fell from 19.1 to 13.4 a quarter. Average ticket rose from $66.00 to $70.61.
- All 7 interpretable tier x tenure cells declined between 23.5% and 25.9%, with frequency as the dominant driver in each.
- 1,627 customers (16.1%) are attrited. They held 11.4% of Q1 spend and cut transactions by 44.1%, against 27.9% for customers who stayed.

## How to run

Requirements: Python 3.11 and a Kaggle API token in `~/.kaggle/` (Kaggle > Settings > API).

Windows:

```powershell
.\run_all.ps1
```

macOS or Linux:

```bash
./run_all.sh
```

Either script creates `.venv`, installs the pinned `requirements.txt`, and runs `run_all.py`, which:

1. downloads `BankChurners.csv` into `data/raw/` if it is missing
2. profiles the raw data
3. runs the SQL models in DuckDB and exports the marts and the Power BI CSVs
4. rebuilds the decomposition in Python and asserts it matches the SQL within 1e-6
5. writes `docs/results.md` and `outputs/headline_numbers.json`
6. builds `docs/index.html`
7. takes dashboard screenshots if Edge or Chrome is installed
8. checks that every number quoted in the memo, this README and the resume bullets exists in the outputs
9. runs the tests

If the Kaggle download fails, download the file by hand from https://www.kaggle.com/datasets/sakshigoyal7/credit-card-customers and put `BankChurners.csv` in `data/raw/`. The raw data is git-ignored.

To run only the tests: `.venv\Scripts\python -m pytest` (Windows) or `.venv/bin/python -m pytest`.

To publish the dashboard: push to GitHub, then Settings > Pages > Deploy from a branch > `main` and `/docs`.

## Assumptions

Full detail, derivation and sensitivity results are in [ASSUMPTIONS.md](ASSUMPTIONS.md). The ones that matter most:

1. **Quarterly values are derived.** If a customer's quarterly values move in a straight line, Q1 + Q4 equals half the 12-month total. With `r` as the Q4/Q1 ratio from the data, `Q1 = total / (2 * (1 + r))` and `Q4 = r * Q1`. This is applied to both spend and transaction count.
2. **Sensitivity.** Under two alternative assumptions (all change in Q4, or all change right after Q1) the decline is between 24.1% and 26.0%, frequency stays the dominant driver, and no interpretable segment changes rank. Dollar levels are less stable than percentages.
3. **Active** means at least one transaction in the quarter. Only 7 customers are inactive in Q4, so this factor is close to flat in this dataset.
4. **Attrition has no date.** Scenario B assumes attrited customers are gone by the end of Q4.

## Limitations

- One Q1 and one Q4. Seasonality cannot be separated from trend.
- The decomposition is descriptive. It shows which factor moved, not why.
- Premium tiers are too small to read.
- In scenario B the portfolio-level customers effect prices each lost customer at the portfolio average. The attrition page shows the cohort view next to it.
- The Power BI report has to be assembled by hand from the build guide. The DAX was written without Power BI Desktop and must be checked against `powerbi/expected_values.csv`.
- This is a public teaching dataset. Nothing here describes a real issuer.
