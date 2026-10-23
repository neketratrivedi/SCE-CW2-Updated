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

-   Fast: 4--5 minutes
-   Medium: 5--7 minutes
-   Slow: 8--10 minutes

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

The script may be updated over time, so the exact outputs depend on the
version being run. If a listed output is not generated, check that the
corresponding code block executes and that the input data contains the
expected columns.


