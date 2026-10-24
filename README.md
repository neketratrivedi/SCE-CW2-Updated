# HyperBasket Casework --- Task 1

## Overview

`task1.py` analyzes the historical HyperBasket order data for **Task 1:
Characterize demand**. It produces descriptive statistics,
visualizations, and CSV files intended to support the later ordering and
replenishment tasks.

The script covers:

-   **Task 1(a): Demand characterization** --- SKU-level daily demand
    statistics, weekday and monthly seasonality, a simple linear trend,
    time-varying monthly variability, and next-year daily demand
    estimates.
-   **Task 1(b): Order timing** --- order volume by weekday, hour of
    day, and broad time-of-day period; identifies peak days and hours.
-   **Task 1(c): Basket size** --- basket-size distribution and a
    validation check comparing the order-level basket size against
    summed order-line quantities.
-   **Task 1(d): Product associations** --- counts SKU pairs appearing
    in the same order and calculates support, confidence, and lift.
-   **Task 1(e): Temperature zones** --- temperature-zone combinations,
    number of zones per order, zone presence probabilities, and the
    relationship between basket line count and zone count.
-   **Task 1(f): Order-to-staging (OTS) budget** --- calculates OTS
    budgets for 20-, 30-, and 45-minute delivery promises, summarizes
    their distributions, and checks negative or missing budgets.

## Files and folder structure


The script reads these three input files:

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `QF_Facility_SKU_Master.csv`        SKU master list; used to include
                                      the full assortment in demand
                                      calculations.

  `QF_Facility_Order_Lines.csv`       Product/SKU lines and quantities
                                      associated with each order; used
                                      for demand, basket, pair, and
                                      temperature-zone analyses.

  `QF_Facility_Orders.csv`            Order-level details, including
                                      placement timestamps, basket size,
                                      and estimated delivery time.
  -----------------------------------------------------------------------

The script expects the input data to contain the column names referenced
in the code, including fields such as `sku_id`, `order_id`, `quantity`,
`temperature_zone`, `placement_timestamp`, `basket_size_units`, and
`estimated_delivery_minutes`.

## Requirements

Use Python 3.10 or a compatible version supported by the installed
packages. Required libraries:

-   `pandas`
-   `numpy`
-   `matplotlib`
-   `statsmodels` (imported in the script, although it is not used in
    the current calculations)


## Methodology summary

### A. SKU-level demand and estimates

Order-line quantities are aggregated by date and SKU. The analysis then
creates a complete date/SKU/hour index and fills absent combinations
with zero. Daily SKU totals are calculated from this table, and summary
statistics include mean, standard deviation, variance, the proportion of
zero-demand days, and coefficient of variation.

Weekday and month factors are calculated relative to each SKU's
historical average. A linear slope is fitted to each SKU's daily demand
over time. The next 365 days are estimated using the SKU baseline,
weekday factor, month factor, and a clipped trend multiplier. Monthly
standard deviation is used as the time-varying variability estimate,
with SKU-level standard deviation as a fallback.

**Interpretation note:** this is a transparent baseline forecasting
approach, not a validated probabilistic demand model. The trend is
linear, seasonal factors are estimated from the historical year, and the
trend multiplier is clipped to limit extreme values. Forecast accuracy
should be assessed separately if actual future observations become
available.

### B. Order timing

Orders are grouped by weekday, hour, and broad periods of the day. The
analysis includes zero-order dates/hours in the hourly grid so that
averages are not calculated only over hours in which orders occurred.
Peak periods are identified using observed average order counts or
demand.

### C. Basket size

The script summarizes the distribution of `basket_size_units` and
calculates the percentage of orders at each basket size. It also
independently sums `quantity` by `order_id` from the order-line file and
compares this value with the order-level basket-size field. Any nonzero
difference should be investigated as a data-quality issue.

### D. Product pairs

For each order, the script identifies distinct SKUs and counts each
unordered pair at most once per order. It calculates:

-   **Support:** share of all orders containing both products.
-   **Confidence A → B:** share of orders containing A that also contain
    B.
-   **Confidence B → A:** share of orders containing B that also contain
    A.
-   **Lift:** co-occurrence relative to what would be expected if
    product occurrences were independent.

The code filters pairs to those appearing together in at least 20
orders. This is a **screening threshold**, not a statistical
significance test. High-frequency pairs should be interpreted separately
from high-lift pairs, and filtered pairs should not automatically be
described as statistically significant.

### E. Temperature-zone combinations

Each order is assigned the distinct temperature zones represented by its
order lines. The script estimates the share of orders for each exact
zone combination and the distribution across one, two, or three zones.
It also cross-tabulates zone count against basket line-count groups.

These are empirical composition probabilities. They do not directly
measure picking time, staging time, labor, or fulfillment cost.

### F. Order-to-staging budget

For each order and each promise duration (p `\in `{=tex}{20,30,45}), the
script calculates:

\[ B_j\^{(p)} = p - D_j, \]

where (D_j) is `estimated_delivery_minutes`. It reports descriptive
statistics and the share of budgets that are negative or missing.

The script also compares budgets with the ranges currently defined in
the code:

-   20 minutes
-   30 minutes
-   40 minutes

**Important interpretation caution:** the same ranges are applied to
each of the three delivery-promise durations. These percentages should
not be treated as a valid comparison of Fast, Medium, and Slow
replenishment scenarios unless the assignment explicitly defines these
ranges in that way. Confirm the scenario definitions in the casework
brief before using those results in conclusions.

## Outputs

The script writes the following files to `outputs/` (some additional
console summaries and interactive plots are also produced):

  -----------------------------------------------------------------------------
  Output                                    Contents
  ----------------------------------------- -----------------------------------
  `demand_estimates.csv`                    SKU/date demand estimates with
                                            `sku_id`, `date`, `mean_units`, and
                                            `sd_units`; intended as a Phase 2
                                            input.

  `1c_basket_size_distribution.csv`         Basket size, number of orders, and
                                            percentage of orders.

  `1c_basket_size_validation.csv`           Order-level comparison of recorded
                                            and recalculated basket sizes.

  `1d_reliable_product_pairs.csv`           SKU pairs passing the minimum
                                            co-occurrence threshold, with
                                            association metrics.

  `1e_zone_count_probabilities.csv`         Distribution of orders by number of
                                            distinct temperature zones.

  `1e_zone_combination_probabilities.csv`   Empirical probabilities for exact
                                            temperature-zone combinations.

  `1e_zone_mix.csv`                         Percentage of orders by
                                            temperature-zone combination.

  `1e_zones_by_basket_size.csv`             Zone-count distribution by basket
                                            line-count group.

  `1e_lines_per_zone.csv`                   Average number of lines per zone
                                            among orders containing that zone.

  `1e_zone_mix.png`                         Bar chart of temperature-zone
                                            combinations.

  `1f_ots_budget_summary.csv`               Descriptive statistics for the
                                            three OTS budget columns.

  `1f_ots_scenario_fit.csv`                 Percentages of budgets falling
                                            inside the coded Fast/Medium/Slow
                                            ranges for each promise duration.

  `1f_ots_budget.png`                       Histogram comparing OTS budgets for
                                            the three delivery promises.

  `1ef_order_features.csv`                  Order-level features used for Task
                                            1(e) and Task 1(f), including zone
                                            and OTS fields.
  -----------------------------------------------------------------------------
HyperBasket Casework — Task 2
Overview

The Task 2 scripts develop and compare ordering alternatives for the HyperBasket Quick Fulfiller (Casework 2, Phase 1, Option A). They use the Task 1 demand estimates to set target stock levels, simulate replenishment over the historical year, and compare the resulting alternatives.

The code covers:

Task 2(a): Autonomy targets — for each replenishment scenario (FAST, MEDIUM, SLOW) and robustness level (50%, 90%, 99%), the autonomy window in days and the target stock in units for every product, plus the three Platform upload files.
Task 2(b): Simulation — a day-by-day simulation of ordering, supplier fills, inventory and stockouts for all 2,000 products over the historical year, with 5 replications per alternative.
Task 2(c): Comparison — summary tables of service, lost units, replenishment quantity, inventory, inbound frequency, space and supplier exposure, by alternative and by temperature zone, and the report figures.
Files and folder structure
project/
├── data/                         input files (see below)
├── main/
│   ├── task2a.py                 shared setup (data, demand estimates, calendars,
│   │                             order-up-to rule) and Task 2(a)
│   ├── task2b.py                 Task 2(b) simulation
│   ├── task2c.py                 Task 2(c) comparison tables
│   ├── task2c_figures.py         Task 2(c) report figures
│   └── task2_main.py             runs 2a → 2b → 2c → figures
└── outputs/                      everything the scripts write

Input files (in data/):

File	Purpose
QF_Facility_SKU_Master.csv	Products: temperature zone, case pack, minimum inbound case packs, unit volume, opening stock
QF_Facility_Supplier_Sequence.csv	Preferred, second and third DC for each product
QF_Facility_Replenishment_Scenarios.csv	Delivery calendars, booking offsets and times for FAST, MEDIUM and SLOW
QF_Facility_Design_Parameters.csv	Supply rule: full-fill probability (0.95) and partial-fill fraction (0.90)
QF_Facility_Orders.csv, QF_Facility_Order_Lines.csv	Historical orders, replayed as demand in the simulation
demand_estimates.csv	Task 1 output: sku_id, date, mean_units, sd_units for 365 days from 2027-09-07

Note: the Orders and Order Lines files must be the full v2 release (2026-10-12). Empty placeholder copies cause EmptyDataError.

Requirements

Python 3.10 or later, with pandas, numpy, scipy and matplotlib.

How to run

From the project folder:

python main/task1.py                    # writes outputs/demand_estimates.csv
# copy outputs/demand_estimates.csv into data/
python main/task2_main.py               # runs Task 2(a), 2(b), 2(c) and the figures

Run time: a few minutes (45 simulated years: 9 alternatives × 5 replications).

Settings at the top of task2a.py:

Setting	Default	Meaning
SCENARIOS	FAST, MEDIUM, SLOW	Replenishment scenarios
SERVICE_TARGETS	0.50, 0.90, 0.99	Robustness levels R
N_REPS	5	Replications per alternative
BASE_SEED	20261020	Replication k uses seed BASE_SEED + k, the same for every alternative
SIM_MODE	historical	historical replays the actual order lines; forecast draws demand from the estimates
SCALE_PLAN	False	True runs the sensitivity case T2-SENS (plan scaled to the historical demand level)
Methodology summary

A. Autonomy targets (2a). For each booking, the coverage window runs from the first moment not yet covered (the booking day, or the next day after an 18:00 booking) until the following delivery arrives. Target stock is the R-quantile of demand over that window, using the Task 1 mean and variance summed over the days in the window (days treated as independent). The quantile is negative binomial when variance exceeds the mean, Poisson otherwise. Each target holds from its booking until the next booking. Autonomy in days is reported as target stock ÷ average daily demand in the window.

B. Simulation (2b). Each day: deliveries are placed on the shelves at 06:00; 08:00 bookings are placed; the day's actual demand is served from stock (unmet demand is lost); 18:00 bookings are placed after trading. At each booking the order quantity raises the inventory position (on hand + on order) to the target, rounded up to case packs and the minimum inbound quantity. The supplier fills the order in full with probability 0.95; otherwise 90% ships and the remainder goes to the next DC in the sequence on that DC's next delivery day; anything left after the third DC is lost. Deliveries due early in the year that would have been booked before day 0 are placed at the start, so the simulation has no artificial start-up gap.

C. Comparison (2c). Results are summed over products and averaged over replications. Measures: inventory service (units supplied ÷ units demanded) with a 95% confidence interval, lost units, supplier orders and average order size, total units ordered, average and peak stock (units and m³), stockout product-days, partial fills, unfillable units and their share of units ordered, and autonomy days (plain and demand-weighted average).

Interpretation notes:

Because every replication replays the same historical demand, only supplier fills vary between replications; the confidence intervals therefore understate real uncertainty.
The planning estimates in demand_estimates.csv total about 14% less than the historical year. The run T2-SENS (SCALE_PLAN = True) shows the effect of planning at the historical level.
Peak space is the sum of each product's own peak stock, which do not occur on the same day, so it is an upper bound.
Outputs

Written to outputs/:

Output	Contents
ordering_alternative_A50.csv, _A90.csv, _A99.csv	Platform upload files: policy_id, scenario_id, service_target, sku_id, effective_day, target_stock_units for every product, scenario and day from 2027-09-07 to 2027-12-27 (672,000 rows each)
2a_autonomy_targets.csv	Per product, scenario and R: preferred and serving DC, autonomy days (window, nominal, target), average daily demand, average target units
2b_simulation_by_sku.csv	Per product, alternative and replication: demand, served, lost, stockout days, orders, units ordered, partial fills, supplier-lost units, average and peak stock
2c_comparison_summary.csv	One row per alternative: all comparison measures (Table 1 of the report)
2c_comparison_by_zone.csv	Service and average stock volume by temperature zone
2c_comparison_summary_level_corrected.csv	Same as the summary for run T2-SENS (rename after running with SCALE_PLAN = True)
2c_service_vs_volume.png	Figure 1: service vs average stock volume
2c_inbound.png	Figure 2: supplier orders per year and order size
2c_volume_by_zone.png	Figure 3: average stock by zone and summed peak space
Experiment register
Run ID	Command and settings	Seeds	Outputs used in report
T2-01	task2_main.py, defaults	20261020–20261024	All Task 2 outputs above, Figures 1–3
T2-SENS	task2_main.py, SCALE_PLAN = True	20261020–20261024	2c_comparison_summary_level_corrected.csv, dashed lines in Figure 1



