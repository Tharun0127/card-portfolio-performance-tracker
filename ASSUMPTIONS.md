# Assumptions

This project answers a quarter-on-quarter question with a dataset that does not contain
quarterly values. That gap is filled with an assumption. This file states the assumption,
shows where it comes from, tests it against two alternatives, and lists every other
modelling choice. Numbers quoted here come from `docs/results.md`.

## 1. What the data has and what it lacks

Per customer, the file gives:

| Column | Meaning |
|---|---|
| `Total_Trans_Amt` | Spend over the last 12 months |
| `Total_Trans_Ct` | Transaction count over the last 12 months |
| `Total_Amt_Chng_Q4_Q1` | Q4 spend divided by Q1 spend |
| `Total_Ct_Chng_Q4_Q1` | Q4 transaction count divided by Q1 transaction count |

It does not give Q1 or Q4 levels. One total and one ratio are two facts about four
unknown quarters, so the levels cannot be recovered without assuming something about
Q2 and Q3.

## 2. Base case: linear trend

**Assumption.** Within the year, a customer's quarterly value moves in a straight line
from Q1 to Q4.

**Derivation.** Write the four quarters as

```
Q1 = a
Q2 = a + d
Q3 = a + 2d
Q4 = a + 3d
```

Then

```
total   = Q1 + Q2 + Q3 + Q4 = 4a + 6d
Q1 + Q4 = 2a + 3d           = total / 2
```

The data gives `r = Q4 / Q1`, so `Q4 = r * Q1`. Substituting:

```
Q1 + r * Q1 = total / 2
Q1 = total / (2 * (1 + r))
Q4 = r * Q1
```

The same formula is applied to spend (with the amount ratio) and to transaction count
(with the count ratio), customer by customer.

**Worked example.** A customer with a 12-month spend of $4,000 and an amount ratio of 0.6:

```
Q1 = 4000 / (2 * 1.6) = 1,250.00
Q4 = 0.6 * 1250       =   750.00
Q2 = 1,083.33 and Q3 = 916.67 (evenly spaced between Q1 and Q4)
Check: 1250 + 1083.33 + 916.67 + 750 = 4,000
```

**What the assumption does and does not affect.**

- Each customer's own Q4/Q1 ratio is taken from the data. The assumption never changes it.
- The assumption sets the level of Q1 and Q4, which decides how much weight each customer
  gets when ratios are averaged into a portfolio or segment figure. Portfolio Q4/Q1 is
  the Q1-weighted average of customer ratios, and the Q1 weights depend on the assumption.
- Derived transaction counts are not whole numbers. They are estimates of a level, not
  literal counts.

**Where it could be wrong.** Real card spend is seasonal and lumpy. A customer who made
one large purchase in Q2 does not follow a straight line. The assumption is reasonable
on average across ten thousand customers and unreliable for any single customer.

## 3. Sensitivity check

Two alternatives sit on either side of the base case:

| Name | Assumption | Formula for Q1 |
|---|---|---|
| Linear (base) | Q2 and Q3 on a straight line between Q1 and Q4 | `total / (2 + 2r)` |
| Early step | Q2 = Q3 = Q1, all the change happens in Q4 | `total / (3 + r)` |
| Late step | Q2 = Q3 = Q4, all the change happens right after Q1 | `total / (1 + 3r)` |

In all three, `Q4 = r * Q1`. For the example customer above, Q1 would be $1,111.11 under
the early step and $1,428.57 under the late step, against $1,250.00 in the base case.
The brief asked for one alternative. The second one is included because the two together
bracket the base case from both sides.

**Portfolio results under each assumption**

| Scenario | Assumption | Q1 spend | Q4 spend | % change | Customers | Active rate | Txns per active | Avg ticket |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A. As observed | Linear (base) | $12.74M | $9.56M | -25.0% | 0.0% | 0.2% | 123.2% | -23.5% |
| A. As observed | Early step | $11.87M | $9.00M | -24.1% | 0.0% | 0.3% | 122.7% | -22.9% |
| A. As observed | Late step | $13.85M | $10.25M | -26.0% | 0.0% | 0.2% | 124.3% | -24.5% |
| B. Q4 exit run-rate | Linear (base) | $12.74M | $8.50M | -33.3% | 43.2% | 0.0% | 69.5% | -12.7% |
| B. Q4 exit run-rate | Early step | $11.87M | $8.00M | -32.6% | 44.4% | 0.0% | 66.5% | -11.0% |
| B. Q4 exit run-rate | Late step | $13.85M | $9.11M | -34.2% | 41.8% | 0.0% | 73.3% | -15.1% |

The last four columns are each factor's share of the spend change.

**Conclusions that survive all three assumptions**

1. Spend falls by about a quarter as observed (between 24.1% and 26.0%) and by about a
   third on an exit run-rate basis (between 32.6% and 34.2%).
2. Transactions per active customer is the dominant driver in both scenarios.
3. Average ticket rises and offsets part of the decline.
4. Active rate explains almost nothing.
5. Among the 7 interpretable tier x tenure cells, no cell changes its contribution rank
   or its dominant driver.

**What does not survive**

1. Dollar levels. Q1 spend ranges from $11.87M to $13.85M depending on the assumption.
   Any dollar figure in this project is an estimate under the base case, not a measured
   value. Percentages and shares are much more stable than dollars.
2. The exact split between customers and frequency in scenario B. The customers share
   moves between 41.8% and 44.4%, and the frequency share between 66.5% and 73.3%. The
   ordering does not change.

## 4. Other assumptions and rules

| Topic | Rule | Reason and effect |
|---|---|---|
| Active customer | Active in a quarter if the quarterly transaction count is above zero. In Q4 that means `Total_Ct_Chng_Q4_Q1 > 0`. Everyone is active in Q1, because a Q4/Q1 ratio can only exist when Q1 is positive. | The flag comes straight from the data and is identical under all three quarterly assumptions. 7 customers are inactive in Q4. A stricter reading (derived Q4 count of at least 1) would add 12 more customers under the base case. Either way the active rate stays above 99.8%. |
| Inconsistent rows | If the count ratio is zero, Q4 spend is set to zero even if the amount ratio is positive. | No transactions means no spend. Affects 2 customers. |
| Scenario A, as observed | The same 10,127 customers are on book in Q1 and Q4. | Isolates behaviour change. The customers effect is zero by construction. |
| Scenario B, Q4 exit run-rate | The 1,627 customers flagged "Attrited Customer" are on book in Q1 and off book at Q4 end. Their Q4 spend and transactions are removed. | Shows the book the team carries into the next year. It is a run-rate view, not a record of what was billed in Q4. |
| Q1 book | Every customer is treated as on book in Q1. | The shortest tenure in the file is 13 months, so every customer was on book for the whole 12-month window. |
| Tenure bands | 13-24, 25-36, 37-48, 49+ months from `Months_on_book`. | Specified in the brief. 2,463 customers have exactly 36 months, which looks like imputation by the data provider and inflates the 25-36 band. |
| Low n | A tier x tenure cell with fewer than 50 customers on the Q1 book is flagged "low n, not interpreted". | 8 of the 15 populated cells are flagged. Platinum has 20 customers and Gold 116, so neither tier supports a conclusion. |
| Decomposition method | Additive LMDI. Cells with a zero factor use sequential substitution and are flagged. | In the real data the only zero-factor cell is the attrited cohort in scenario B, which has no Q4 customers. |
| Dropped columns | The two columns starting with `Naive_Bayes_Classifier` are dropped in staging. | They are model outputs left in the public file and leak the attrition label. |

## 5. What cannot be checked with this data

- **Seasonality.** There is one Q1 and one Q4. A 25% fall could be a seasonal pattern, a
  trend, or both. In a real card portfolio Q4 is usually the strongest quarter, so a
  fall this size would be unusual. The file does not say which calendar months the
  quarters cover.
- **When attrition happened.** The attrition flag has no date. Scenario B assumes the
  attrited customers are gone by the end of Q4. If some left earlier, part of their low
  Q4 activity is the closure itself.
- **Causality.** A decomposition says which factor moved, not why it moved.
- **Representativeness.** This is a public teaching dataset of unknown origin. Nothing
  here describes any real issuer.
