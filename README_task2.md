# HyperBasket Casework — Task 2

## Overview

The Task 2 scripts develop and compare **ordering alternatives** for the HyperBasket Quick Fulfiller (Casework 2, Phase 1, Option A). They use the Task 1 demand estimates to set target stock levels, simulate replenishment over the historical year, and compare the resulting alternatives.

The code covers:

- **Task 2(a): Autonomy targets** — for each replenishment scenario (FAST, MEDIUM, SLOW) and robustness level (50%, 90%, 99%), the autonomy window in days and the target stock in units for every product, plus the three Platform upload files.
- **Task 2(b): Simulation** — a day-by-day simulation of ordering, supplier fills, inventory and stockouts for all 2,000 products over the historical year, with 5 replications per alternative.
- **Task 2(c): Comparison** — summary tables of service, lost units, replenishment quantity, inventory, inbound frequency, space and supplier exposure, by alternative and by temperature zone, and the report figures.

## Files and folder structure

```
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
```

Input files (in `data/`):

| File | Purpose |
| --- | --- |
| `QF_Facility_SKU_Master.csv` | Products: temperature zone, case pack, minimum inbound case packs, unit volume, opening stock |
| `QF_Facility_Supplier_Sequence.csv` | Preferred, second and third DC for each product |
| `QF_Facility_Replenishment_Scenarios.csv` | Delivery calendars, booking offsets and times for FAST, MEDIUM and SLOW |
| `QF_Facility_Design_Parameters.csv` | Supply rule: full-fill probability (0.95) and partial-fill fraction (0.90) |
| `QF_Facility_Orders.csv`, `QF_Facility_Order_Lines.csv` | Historical orders, replayed as demand in the simulation |
| `demand_estimates.csv` | Task 1 output: `sku_id, date, mean_units, sd_units` for 365 days from 2027-09-07 |

Note: the Orders and Order Lines files must be the full v2 release (2026-10-12). Empty placeholder copies cause `EmptyDataError`.

## Requirements

Python 3.10 or later, with `pandas`, `numpy`, `scipy` and `matplotlib`.

## How to run

From the project folder:

```
python main/task1.py                    # writes outputs/demand_estimates.csv
# copy outputs/demand_estimates.csv into data/
python main/task2_main.py               # runs Task 2(a), 2(b), 2(c) and the figures
```

Run time: a few minutes (45 simulated years: 9 alternatives × 5 replications).

Settings at the top of `task2a.py`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `SCENARIOS` | FAST, MEDIUM, SLOW | Replenishment scenarios |
| `SERVICE_TARGETS` | 0.50, 0.90, 0.99 | Robustness levels R |
| `N_REPS` | 5 | Replications per alternative |
| `BASE_SEED` | 20261020 | Replication *k* uses seed BASE_SEED + *k*, the same for every alternative |
| `SIM_MODE` | `historical` | `historical` replays the actual order lines; `forecast` draws demand from the estimates |
| `SCALE_PLAN` | False | True runs the sensitivity case T2-SENS (plan scaled to the historical demand level) |

## Methodology summary

**A. Autonomy targets (2a).** For each booking, the coverage window runs from the first moment not yet covered (the booking day, or the next day after an 18:00 booking) until the following delivery arrives. Target stock is the R-quantile of demand over that window, using the Task 1 mean and variance summed over the days in the window (days treated as independent). The quantile is negative binomial when variance exceeds the mean, Poisson otherwise. Each target holds from its booking until the next booking. Autonomy in days is reported as target stock ÷ average daily demand in the window.

**B. Simulation (2b).** Each day: deliveries are placed on the shelves at 06:00; 08:00 bookings are placed; the day's actual demand is served from stock (unmet demand is lost); 18:00 bookings are placed after trading. At each booking the order quantity raises the inventory position (on hand + on order) to the target, rounded up to case packs and the minimum inbound quantity. The supplier fills the order in full with probability 0.95; otherwise 90% ships and the remainder goes to the next DC in the sequence on that DC's next delivery day; anything left after the third DC is lost. Deliveries due early in the year that would have been booked before day 0 are placed at the start, so the simulation has no artificial start-up gap.

**C. Comparison (2c).** Results are summed over products and averaged over replications. Measures: inventory service (units supplied ÷ units demanded) with a 95% confidence interval, lost units, supplier orders and average order size, total units ordered, average and peak stock (units and m³), stockout product-days, partial fills, unfillable units and their share of units ordered, and autonomy days (plain and demand-weighted average).

Interpretation notes:

- Because every replication replays the same historical demand, only supplier fills vary between replications; the confidence intervals therefore understate real uncertainty.
- The planning estimates in `demand_estimates.csv` total about 14% less than the historical year. The run T2-SENS (`SCALE_PLAN = True`) shows the effect of planning at the historical level.
- Peak space is the sum of each product's own peak stock, which do not occur on the same day, so it is an upper bound.

## Outputs

Written to `outputs/`:

| Output | Contents |
| --- | --- |
| `ordering_alternative_A50.csv`, `_A90.csv`, `_A99.csv` | Platform upload files: `policy_id, scenario_id, service_target, sku_id, effective_day, target_stock_units` for every product, scenario and day from 2027-09-07 to 2027-12-27 (672,000 rows each) |
| `2a_autonomy_targets.csv` | Per product, scenario and R: preferred and serving DC, autonomy days (window, nominal, target), average daily demand, average target units |
| `2b_simulation_by_sku.csv` | Per product, alternative and replication: demand, served, lost, stockout days, orders, units ordered, partial fills, supplier-lost units, average and peak stock |
| `2c_comparison_summary.csv` | One row per alternative: all comparison measures (Table 1 of the report) |
| `2c_comparison_by_zone.csv` | Service and average stock volume by temperature zone |
| `2c_comparison_summary_level_corrected.csv` | Same as the summary for run T2-SENS (rename after running with `SCALE_PLAN = True`) |
| `2c_service_vs_volume.png` | Figure 1: service vs average stock volume |
| `2c_inbound.png` | Figure 2: supplier orders per year and order size |
| `2c_volume_by_zone.png` | Figure 3: average stock by zone and summed peak space |

## Experiment register

| Run ID | Command and settings | Seeds | Outputs used in report |
| --- | --- | --- | --- |
| T2-01 | `task2_main.py`, defaults | 20261020–20261024 | All Task 2 outputs above, Figures 1–3 |
| T2-SENS | `task2_main.py`, `SCALE_PLAN = True` | 20261020–20261024 | `2c_comparison_summary_level_corrected.csv`, dashed lines in Figure 1 |
