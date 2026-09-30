# Memo: why Q4 card spend is below Q1

**To:** Portfolio team, consumer card
**Basis:** 10,127 customers, public Kaggle dataset. Q1 and Q4 are derived estimates (see Limitations).

## Headline

Q4 spend is 25.0% below Q1, $9.56M against $12.74M. The whole decline comes from
customers transacting less often. The number of customers and the share who are active
did not move, and a higher average ticket offset part of the fall. Once attrited
customers are taken off the book, the decline is 33.3%.

## Findings

**1. Frequency explains the decline, not ticket size or activity.**
Transactions per active customer fell 29.8%, from 19.1 to 13.4 a quarter. That removed
$3.92M of spend, which is 123.2% of the net decline. Average ticket rose 7.0%, from $66.00
to $70.61, and added back $0.75M. The active rate is 99.93% in Q4: only 7 customers
stopped transacting, worth $7,657.

**2. The decline is portfolio-wide, not a tier or tenure problem.**
All 7 tier x tenure cells with enough customers to read fell between 23.5% and 25.9%, and
frequency is the dominant driver in all 7. No cell explains much more or less of the
decline than its size predicts (over-index between 0.94 and 1.04). Blue customers with
25 to 48 months on book hold 77.2% of Q1 spend and account for 78.1% of the decline
($2.49M). Gold (116 customers) and Platinum (20 customers) are too small to interpret.

**3. Attrition deepens the decline, and leavers show it in frequency first.**
1,627 customers (16.1%) are flagged as attrited. They held 11.4% of Q1 spend, because they
spend 32.7% less per head than customers who stay. Removing them takes the Q4 run-rate
to $8.50M, and lost customers then explain 43.2% of the decline. Before leaving, attrited
customers cut their transactions by 44.1%, against 27.9% for customers who stayed.

## Recommendations

**1. Aim the recovery at transaction frequency in the Blue core, and track it directly.**
The lever is how often the card is used, not how much is spent per use. Test everyday
spend and recurring payment offers on Blue customers with 25 to 48 months on book, and
make transactions per active customer the lead KPI. Blue accounts for 90.0% of the
$3.18M decline, so a programme limited to the premium tiers would miss most of it.

**2. Use a falling transaction count as the retention trigger, ranked by spend.**
Attrited customers carry $1.06M of Q4 spend, 11.1% of the quarter. They already
transacted less than stayers in Q1 (14.4 against 20.0 transactions per customer) and the
gap widened by Q4. Prioritise outreach by spend at risk, since leavers are below-average
spenders and a headcount target would overstate what retention can recover.

## Limitations

- **Derived quarters.** The data has 12-month totals and Q4/Q1 ratios only. Q1 and Q4 are
  estimated with a linear trend assumption. Under two alternative assumptions the decline
  is between 24.1% and 26.0%, and the ranking of drivers and segments does not change.
  Dollar levels are less certain than percentages.
- **No seasonality.** There is one Q1 and one Q4, so a seasonal pattern cannot be
  separated from a trend.
- **Attrition timing is unknown.** The flag has no date. Part of the leavers' low Q4
  frequency may be the closure itself, which would weaken it as an early signal.
- **Descriptive, not causal.** The decomposition shows which factor moved, not why.
  Both recommendations are hypotheses to test.
