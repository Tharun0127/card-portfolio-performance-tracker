# Power BI build guide

This guide builds a 4-page report in Power BI Desktop from the CSV files in this folder.
Allow about 60 to 90 minutes the first time.

**Status of this guide.** The CSV files and the logic behind the measures are tested by
the pipeline (`tests/test_pipeline.py` recomputes every slicer combination from the star
schema). The DAX text and the report itself were written without Power BI Desktop to
hand, so they have not been run. Step 6 is a check table. Do not skip it.

## Files in this folder

| File | Role | Rows |
|---|---|---:|
| `fact_customer_quarter.csv` | Fact. One row per scenario x customer x quarter on book | 38,881 |
| `dim_customer.csv` | Customer attributes, attrition flag | 10,127 |
| `dim_tier.csv` | Card tiers | 4 |
| `dim_tenure.csv` | Tenure bands | 4 |
| `dim_scenario.csv` | Scenario A and B | 2 |
| `dim_bridge_step.csv` | Helper for the waterfall axis. Not related to any table | 5 |
| `measures.dax` | Every measure, commented | |
| `theme.json` | Colours and fonts that match `docs/index.html` | |
| `expected_values.csv` | Results from the SQL pipeline to check the report against. Do not load into the model | 48 |

The fact table holds base-case (linear assumption) values only. Off-book rows are not
stored: in scenario B an attrited customer has a Q1 row and no Q4 row.

`dim_bridge_step` is one table more than a strict star needs. The native waterfall
visual needs a column for its axis, and the steps of a bridge (Q1 spend, four effects)
are not an attribute of any customer, so they sit in a small disconnected table.

## Step 1. Load the data

1. Home > Get data > Text/CSV. Load the six CSV files listed as fact, dim or helper above.
   Choose Transform Data for each so you can check the types.
2. In Power Query set these types. If your Windows region uses a comma as the decimal
   separator, use "Change type > Using locale > English (United States)" for the decimal
   columns.

| Table | Column | Type |
|---|---|---|
| fact_customer_quarter | scenario_key, customer_id, tier_key, tenure_key, is_active | Whole number |
| fact_customer_quarter | quarter | Text |
| fact_customer_quarter | txn_count, spend | Decimal number |
| dim_customer | customer_id, cell_customers, months_on_book, customer_age, relationship_count, months_inactive_12m, contacts_12m | Whole number |
| dim_customer | credit_limit | Decimal number |
| dim_customer | all other columns | Text |
| dim_tier | tier_key, customers | Whole number |
| dim_tenure | tenure_key, min_months_on_book, max_months_on_book, customers | Whole number |
| dim_scenario | scenario_key | Whole number |
| dim_bridge_step | step_key | Whole number |

3. Close & Apply.
4. Home > Enter data. Create a table named `_Measures` with one column and no rows that
   matter (leave the default cell). This table will hold the measures.
5. View > Themes > Browse for themes > `theme.json`.

## Step 2. Relationships

Model view. Create these four relationships, all many-to-one, single direction
(dimension filters fact), active:

| From (many) | To (one) |
|---|---|
| fact_customer_quarter[customer_id] | dim_customer[customer_id] |
| fact_customer_quarter[tier_key] | dim_tier[tier_key] |
| fact_customer_quarter[tenure_key] | dim_tenure[tenure_key] |
| fact_customer_quarter[scenario_key] | dim_scenario[scenario_key] |

`dim_bridge_step` and `_Measures` have no relationships. If Power BI auto-detected any
other relationship, delete it.

## Step 3. Column settings

1. Sort by column (Data view, select the column, Column tools > Sort by column):
   - dim_tier[card_tier] sorted by dim_tier[tier_key]
   - dim_tenure[tenure_band] sorted by dim_tenure[tenure_key]
   - dim_scenario[scenario_name] sorted by dim_scenario[scenario_key]
   - dim_bridge_step[step] sorted by dim_bridge_step[step_key]
2. Set "Don't summarize" on every key column and on customer_id.
3. Hide in report view: all key columns in the fact table, fact_customer_quarter[txn_count],
   [spend] and [is_active] (the measures replace them), and the placeholder column in
   `_Measures`.

## Step 4. Measures

Option 1 (fast). Open DAX query view, paste the whole of `measures.dax`, press Run, then
click "Update model with changes" above the DEFINE block. All measures are added to
`_Measures`.

Option 2 (by hand). For each `MEASURE '_Measures'[Name] = expression` block in the file,
select `_Measures`, click New measure, and paste `Name = expression`.

Then set the formats (select the measure, Measure tools > Format):

| Format | Measures |
|---|---|
| Whole number, thousands separator | Customers Q1, Customers Q4, Active Customers Q1, Active Customers Q4, Attrited Customers |
| Currency, 0 decimals | Spend Q1, Spend Q4, Spend Change, Effect Customers, Effect Active Rate, Effect Txns per Active, Effect Avg Ticket, Dominant Effect, Bridge Value, Log Mean Spend, Spend per Customer Q1, Spend per Customer Q4, Attrited Q4 Spend As Observed, Spend Change Exit Run-Rate |
| Currency, 2 decimals | Avg Ticket Q1, Avg Ticket Q4, Effect Check |
| Decimal number, 2 decimals | Txns Q1, Txns Q4, Txns per Active Q1, Txns per Active Q4, Txns per Customer Q1, Txns per Customer Q4, Over Index |
| Percentage, 2 decimals | Active Rate Q1, Active Rate Q4, Active Rate Change pts |
| Percentage, 1 decimal | Spend Change %, Customers Change %, Txns per Active Change %, Avg Ticket Change %, Share Customers, Share Active Rate, Share Txns per Active, Share Avg Ticket, Share of Portfolio Change, Share of Q1 Spend, Share of Q1 Customers, Contribution pts, Spend per Customer Change %, Txns per Customer Change %, Attrition Rate, Attrited Share of Q1 Spend, Spend Change % Exit Run-Rate, Heatmap Value |
| Text (no format) | Decomposition Method, Dominant Driver, Sample Flag, Heatmap Label, Title KPI, Title Bridge, Title Heatmap, Title Attrition |

## Step 5. Build the pages

Canvas: View > Page view > Fit to page. Format > Canvas settings > 16:9 (1280 x 720).
Positions below are x, y, width, height in pixels (Format > General > Properties).

Every chart title must state the takeaway. Where a title measure exists, bind it:
Format > General > Title > the fx button > Format style: Field value > pick the measure.
Where there is no title measure, type the title given below and recheck it against the
numbers before publishing.

Shared elements on pages 1 to 3:

| Visual | Position | Setup |
|---|---|---|
| Text box, report title | 20, 10, 800, 40 | "Card Portfolio Performance Tracker", 18 pt semibold |
| Slicer, scenario | 960, 10, 300, 56 | Field: dim_scenario[scenario_name]. Style: Tile. Selection: Single select on |
| Text box, footnote | 20, 690, 1240, 24 | "Q1 and Q4 are estimates derived from 12-month totals and Q4/Q1 ratios under a linear trend assumption. See ASSUMPTIONS.md." 9 pt, grey |

Select the scenario slicer on page 1, then View > Sync slicers, and sync it to pages 1, 2
and 3 so the choice carries across pages.

### Page 1. KPI overview

Purpose: the five numbers behind the identity, Q1 against Q4.

| Visual | Position | Fields | Formatting |
|---|---|---|---|
| Card (new) x 5, in a row | y 70, each 236 x 110, x = 20, 272, 524, 776, 1028 | 1: Spend Q4, reference label Spend Change %. 2: Customers Q4, reference label Customers Change %. 3: Active Rate Q4, reference label Active Rate Change pts. 4: Txns per Active Q4, reference label Txns per Active Change %. 5: Avg Ticket Q4, reference label Avg Ticket Change % | Callout 24 pt. Rename labels to "Spend, Q4", "Customers on book, Q4", "Active rate, Q4", "Transactions per active, Q4", "Average ticket, Q4". Reference label title "vs Q1" |
| Clustered bar chart | 20, 200, 610, 470 | Y-axis: leave empty. X-axis: Customers Change %, Active Rate Change pts, Txns per Active Change %, Avg Ticket Change % | Title bound to `Title KPI`. Data labels on. Legend off. Rename the series to the four factor names. One colour for all four bars (#2a78d6) |
| Clustered bar chart | 650, 200, 610, 470 | Y-axis: dim_tier[card_tier]. X-axis: Spend Change %. Tooltips: Customers Q1, Sample Flag | Title: "Spend change by card tier. Gold and Platinum are small samples." Data labels on. Conditional colour on bars: fx > Rules > if `Customers Q1` < 50 then #e1e0d9, else #2a78d6 |

To show tenure on the same page, duplicate the last chart, swap the axis to
dim_tenure[tenure_band], and give each chart half the height (225 px).

### Page 2. Spend bridge

Purpose: the waterfall from Q1 spend to Q4 spend, for any tier and tenure selection.

| Visual | Position | Fields | Formatting |
|---|---|---|---|
| Slicer, tier | 20, 70, 300, 56 | dim_tier[card_tier] | Style: Dropdown. Multi-select is fine, the measures recompute for whatever is selected |
| Slicer, tenure | 340, 70, 300, 56 | dim_tenure[tenure_band] | Style: Dropdown |
| Card, method | 960, 70, 300, 56 | Decomposition Method | 10 pt. Shows when the sequential fallback is in use |
| Waterfall chart | 20, 140, 800, 530 | Category: dim_bridge_step[step]. Y-axis: Bridge Value | Title bound to `Title Bridge`. Sentiment colours: Increase #2a78d6, Decrease #e34948, Total #898781. Data labels on, display units Millions, 2 decimals. Sort axis by step_key ascending (More options > Sort axis > step, ascending, which follows the sort-by column). The visual adds a "Total" column at the end: rename it to "Q4 spend" under Format > X-axis or leave it as Total and say so in the subtitle |
| Table | 840, 140, 420, 330 | dim_bridge_step[step], Bridge Value | Title: "Bridge values". Totals on, label "Q4 spend" |
| Multi-row card | 840, 480, 420, 190 | Share Customers, Share Active Rate, Share Txns per Active, Share Avg Ticket, Customers Q1, Sample Flag | Title: "Share of the spend change by factor" |

Notes:

- The first bar, "Q1 spend", is drawn as an increase from zero. That is how the native
  waterfall starts a bridge. If you want it grey, use Format > Columns > apply settings to
  "Q1 spend" where your version allows per-category colours, otherwise leave it.
- Check that the last column equals `Spend Q4`. If it does not, the waterfall is
  totalling the measure differently in your version: put `Spend Q4` on a card next to it
  and report the card value.
- When a low-n cell is selected, the title switches to "Low n (n customers), not
  interpreted". Leave it that way.

### Page 3. Tier x tenure heatmap

Purpose: spend change and dominant driver for each of the 16 cells.

| Visual | Position | Fields | Formatting |
|---|---|---|---|
| Matrix | 20, 70, 780, 360 | Rows: dim_tier[card_tier]. Columns: dim_tenure[tenure_band]. Values: Heatmap Label | Title bound to `Title Heatmap`. Row and column subtotals off. Text size 10, word wrap on, row padding 12 |
| Matrix conditional formatting | | Cell elements > Background colour > fx. Format style: Gradient. Based on field: `Heatmap Value`. Minimum: custom -0.40, colour #0d366b. Maximum: custom 0, colour #cde2fb. Default formatting (blanks): Specific colour #e1e0d9 | Then Cell elements > Font colour > fx > Rules: if `Heatmap Value` < -0.20 then white, else #0b0b0b. Blank stays #52514e |
| Text box | 20, 440, 780, 50 | | "Grey cells have fewer than 50 customers: low n, not interpreted. Platinum has 20 customers and Gold 116 in total. The colour scale is fixed from 0% to 40% decline." |
| Clustered bar chart | 820, 70, 440, 600 | Y-axis: dim_customer[tier_tenure_cell]. X-axis: Share of Q1 Spend, Share of Portfolio Change. Tooltips: Over Index, Customers Q1 | Title: "Share of the portfolio change against share of Q1 spend: the change follows segment size." Visual-level filter: dim_customer[cell_sample_flag] is "OK". Sort by Share of Portfolio Change descending. Data labels on |
| Table | 20, 500, 780, 170 | dim_customer[tier_tenure_cell], Customers Q1, Spend Change %, Dominant Driver, Over Index, Sample Flag | Title: "Cell detail". Sort by Customers Q1 descending |

The fixed colour scale is deliberate. With an automatic scale a gap of two percentage
points between cells would look like the difference between the best and the worst
segment.

### Page 4. Attrition lens

Purpose: compare attrited and existing customers, and show what attrition removes.

Set a page-level filter: dim_scenario[scenario_name] is "As observed". There is no
scenario slicer on this page. The two exit run-rate measures ignore that filter on
purpose.

| Visual | Position | Fields | Formatting |
|---|---|---|---|
| Card (new) x 4, in a row | y 70, each 300 x 100, x = 20, 333, 646, 959 | 1: Attrited Customers, reference label Attrition Rate. 2: Attrited Share of Q1 Spend. 3: Attrited Q4 Spend As Observed. 4: Spend Change % Exit Run-Rate, reference label Spend Change % | Labels: "Attrited customers", "Their share of Q1 spend", "Q4 spend that leaves with them", "Spend change, exit run-rate (as observed below)" |
| Clustered bar chart | 20, 185, 610, 250 | Y-axis: dim_customer[attrition_flag]. X-axis: Spend per Customer Change %, Txns per Customer Change %, Avg Ticket Change % | Title bound to `Title Attrition`. Data labels on. Legend on top |
| Table | 650, 185, 610, 250 | dim_customer[attrition_flag], Customers Q1, Share of Q1 Customers, Share of Q1 Spend, Spend per Customer Q1, Spend per Customer Q4, Txns per Customer Q1, Txns per Customer Q4, Avg Ticket Q1, Avg Ticket Q4 | Title: "Attrited customers spend less per head and cut transactions harder" |
| Waterfall chart | 20, 450, 610, 230 | Category: dim_customer[attrition_flag]. Y-axis: Spend Change Exit Run-Rate | Title: "Exit run-rate spend change by cohort: stayers spending less, and leavers' Q1 spend". Total column on |
| Clustered bar chart | 650, 450, 610, 230 | Y-axis: dim_tenure[tenure_band]. X-axis: Attrition Rate. Tooltips: Customers Q1, Attrited Customers | Title: "Attrition rate by tenure band". Data labels on. Duplicate with dim_tier[card_tier] if space allows, and grey Platinum with the same colour rule as page 1 |

## Step 6. Check the report against the pipeline

With no tier or tenure selected, the report must show these values. They come from
`expected_values.csv`, which has all 48 slicer combinations.

| Measure | Scenario A, as observed | Scenario B, Q4 exit run-rate |
|---|---:|---:|
| Customers Q1 | 10,127 | 10,127 |
| Customers Q4 | 10,127 | 8,500 |
| Spend Q1 | $12,741,922 | $12,741,922 |
| Spend Q4 | $9,558,169 | $8,495,098 |
| Spend Change | -$3,183,753 | -$4,246,823 |
| Spend Change % | -25.0% | -33.3% |
| Effect Customers | $0 | -$1,834,655 |
| Effect Active Rate | -$7,657 | $0 |
| Effect Txns per Active | -$3,923,189 | -$2,950,466 |
| Effect Avg Ticket | $747,093 | $538,298 |
| Effect Check | $0.00 | $0.00 |
| Dominant Driver | Transactions per active | Transactions per active |

Two more spot checks:

| Selection | Scenario | Spend Change % | Effect Txns per Active | Expected title behaviour |
|---|---|---:|---:|---|
| Blue, 25-36 | A | -24.9% | -$1,858,998 | Normal title |
| Platinum, 25-36 | B | -35.0% | -$6,319 | "Low n (10 customers), not interpreted" |

Also check:

- Select both scenarios in the slicer (turn single select off for a moment). Spend must
  not double. The measures fall back to scenario A.
- On page 4, the waterfall by attrition flag should show Existing Customer -$2,792,091,
  Attrited Customer -$1,454,733, total -$4,246,823.
- `Decomposition Method` should read "Sequential fallback" only when the selection has
  no Q4 customers, for example attrition flag = Attrited Customer under scenario B.

If a number is off by more than rounding, the most likely causes are a wrong column type
from a regional decimal setting, a missing relationship, or an extra auto-detected
relationship.

## Known limits of the Power BI version

- The native waterfall cannot colour the opening bar as a total. The Plotly version in
  `docs/index.html` does.
- The cohort waterfall on page 4 shows two cohort totals. The Plotly version splits the
  stayers' change into frequency and ticket.
- Sensitivity to the quarterly assumption is not in the Power BI model. It is in
  `ASSUMPTIONS.md` and `docs/results.md`.
