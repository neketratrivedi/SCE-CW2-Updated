"""Task 2 - shared setup (settings, data, demand estimates, calendars,
order-up-to rule) and Task 2a: target stock for the evaluation window.
Imported by task2b.py and task2c.py; run task2_main.py for the full task."""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import nbinom, poisson

os.makedirs("outputs", exist_ok=True)
START = pd.Timestamp("2026-09-07")          # day 0 = first day of the historical year
SCENARIOS = ["FAST", "MEDIUM", "SLOW"]
SERVICE_TARGETS = [0.50, 0.90, 0.99]
N_REPS = 5                                  # simulation replications
BASE_SEED = 20261020
H = 365                                     # days simulated
FC_FIRST = 365                              # day index of 2027-09-07, first forecast day
T_MAX = FC_FIRST + 365 + 200                # last day index with demand and calendar
EVAL_START, EVAL_END = "2027-09-07", "2027-12-27"
DC_NAMES = ["Local", "Regional", "National"]
DEMAND_ESTIMATES = "data/demand_estimates.csv"   # sku_id, date, mean_units, sd_units
SIM_MODE = "historical"

#DATA
sku = pd.read_csv("data/QF_Facility_SKU_Master.csv").set_index("sku_id")
seq = pd.read_csv("data/QF_Facility_Supplier_Sequence.csv").set_index("sku_id")
scen = pd.read_csv("data/QF_Facility_Replenishment_Scenarios.csv")
params = pd.read_csv("data/QF_Facility_Design_Parameters.csv")
skus = sku.index.to_numpy()
n_sku = len(skus)
seq = seq.reindex(skus)
pref = seq["preferred_dc"].to_numpy()

P_FULL = float(params.loc[params.parameter == "full_fill_probability", "value"].iloc[0])
P_PART = float(params.loc[params.parameter == "partial_fill_fraction", "value"].iloc[0])
print(f"Supply rule: full fill p={P_FULL}, partial fraction={P_PART}")

case = sku["case_pack_units"].to_numpy()
min_units = (sku["minimum_inbound_order_casepacks"] * sku["case_pack_units"]).to_numpy()
unit_vol = sku["unit_volume_l"].to_numpy()
opening = sku["opening_on_hand_units"].to_numpy().astype(float)
zone = sku["temperature_zone"].to_numpy()

#IF USE HISTORICAL MODE, READ ACTUAL DEMAND
if SIM_MODE == "historical":
    orders = pd.read_csv("data/QF_Facility_Orders.csv", usecols=["order_id", "day"])
    lines = pd.read_csv("data/QF_Facility_Order_Lines.csv").merge(orders, on="order_id")
    actual = (lines.pivot_table(index="day", columns="sku_id", values="quantity",
                                aggfunc="sum", fill_value=0)
              .reindex(index=range(H), columns=skus, fill_value=0)
              .to_numpy().astype(float))

#INPUT DATA
est = pd.read_csv(DEMAND_ESTIMATES, parse_dates=["date"])
fc_dates = pd.date_range(START + pd.Timedelta(days=FC_FIRST), periods=365, freq="D")
est_mean = (est.pivot(index="date", columns="sku_id", values="mean_units")
            .reindex(index=fc_dates, columns=skus))
est_sd = (est.pivot(index="date", columns="sku_id", values="sd_units")
          .reindex(index=fc_dates, columns=skus))

#IN CASE OF MISSING DATA, WARN AND FILL WITH 0
n_missing = int(est_mean.isna().to_numpy().sum())
if n_missing:
    print(f"WARNING: {n_missing} SKU-days missing from the estimates, set to 0")

est_mean = est_mean.fillna(0).to_numpy()
est_var = est_sd.fillna(0).to_numpy() ** 2       # daily variance = sd^2
N_EST = est_mean.shape[0]

if SIM_MODE == "historical":
    ratio = est_mean.sum() / max(actual.sum(), 1e-9)
    print(f"Estimated year total / historical year total = {ratio:.3f}")


def est_index(days, offset):
    """Row of the estimates used for each day index: day - offset, moved by whole
    weeks into the estimate range when outside it (keeps the weekday pattern)."""
    i = np.asarray(days) - offset
    low, high = i < 0, i > N_EST - 1
    i[low] += 7 * np.ceil(-i[low] / 7).astype(int)
    i[high] -= 7 * np.ceil((i[high] - (N_EST - 1)) / 7).astype(int)
    return i


def cumulative(offset):
    """Prefix sums of mean and variance over day indices 0..T_MAX.
    Demand over days [a, b): mean = cmu[b] - cmu[a], var = cvar[b] - cvar[a]
    (days assumed independent, so variances add)."""
    i = est_index(np.arange(T_MAX + 1), offset)
    cmu = np.vstack([np.zeros(n_sku), np.cumsum(est_mean[i], axis=0)])
    cvar = np.vstack([np.zeros(n_sku), np.cumsum(est_var[i], axis=0)])
    return cmu, cvar


FC = cumulative(FC_FIRST)        # estimates on their own dates (Task 2a, forecast sim)
HIST = cumulative(FC_FIRST - 364) if SIM_MODE == "historical" else None
# HIST: historical day t uses the estimate 364 days later (same weekday)


def demand_quantile(m, v, r):
    """r-quantile of window demand with mean m and variance v (per SKU).
    Negative binomial when over-dispersed, Poisson otherwise."""
    m = np.maximum(m, 1e-9)
    q = poisson.ppf(r, m)
    od = v > m * 1.0001
    if od.any():
        n = m[od] ** 2 / (v[od] - m[od])
        p = n / (n + m[od])
        q[od] = nbinom.ppf(r, n, p)
    return np.nan_to_num(q).astype(int)


def sample_demand(seed):
    """One year of demand drawn from the estimates (SIM_MODE = "forecast")."""
    rng = np.random.default_rng(seed)
    m, v = est_mean, est_var
    out = rng.poisson(m).astype(float)
    od = (m > 0) & (v > m * 1.0001)             # mean 0 -> demand 0
    n = m[od] ** 2 / (v[od] - m[od])
    out[od] = rng.negative_binomial(n, n / (n + m[od]))
    return out

def delivery_days(row, first_day, last_day):
    """Day indices (relative to START) with a delivery for this scenario row."""
    days = np.arange(first_day, last_day + 1)
    dates = START + pd.to_timedelta(days, unit="D")
    wd = dates.dayofweek.to_numpy()             # Monday = 0, Sunday = 6
    label = row["scheduled_days"]
    if label == "Every day":
        mask = np.ones(len(days), bool)
    elif label == "Sunday and Thursday":
        mask = (wd == 6) | (wd == 3)
    else:                                       # every 7 / 14 / 28 days from anchor
        step = int(row["interval_pattern_days"])
        anchor = (pd.Timestamp(row["cycle_anchor_date"]) - START).days
        mask = ((days - anchor) % step == 0)
    return days[mask]


def scenario_dc_rules(scenario):
    """For each supplier type: delivery days, booking offset and booking time."""
    rules = {}
    for _, row in scen[scen.scenario_id == scenario].iterrows():
        rules[row["supplier"]] = {
            "served_by": row["served_by_dc"],
            "days": delivery_days(row, -60, T_MAX),
            "offset": int(row["book_day_offset"]),
            "book_1800": row["book_time"] == "18:00",
            "interval": float(row["nominal_interval_days"]),
        }
    return rules


def nominal_autonomy_days(rule):
    """Nominal D = booking lead + nominal interval."""
    return int(np.ceil(rule["offset"] + rule["interval"]))


def booking_events(rule):
    """(booking day, delivery day, next delivery day) for every delivery."""
    days = rule["days"]
    return [(int(days[k]) - rule["offset"], int(days[k]), int(days[k + 1]))
            for k in range(len(days) - 1)]


def window_demand(idx, b, d_next, at_1800, cum):
    """Mean and variance of demand over the coverage window of a booking on day b:
    from the first uncovered moment (day b, or b+1 after an 18:00 booking)
    until the next delivery arrives. Also returns the window length in days."""
    cmu, cvar = cum
    start = max(b + 1 if at_1800 else b, 0)
    m = cmu[d_next, idx] - cmu[start, idx]
    v = cvar[d_next, idx] - cvar[start, idx]
    return m, v, d_next - start


def order_up_to(idx, b, d_next, at_1800, r, cum):
    """Target S for a booking on day b: r-quantile of demand over its window.
    Returns S and the window length in days."""
    m, v, D = window_demand(idx, b, d_next, at_1800, cum)
    return demand_quantile(m, v, r), D


def nanmean_cols(a):
    """Column means ignoring NaN; NaN where a column has no values."""
    ok = ~np.isnan(a)
    n = ok.sum(axis=0)
    return np.where(n > 0, np.where(ok, a, 0).sum(axis=0) / np.maximum(n, 1), np.nan)

#NOW BUILD THE TARGET STOCKS AND AUTONOMY TABLES FOR THE EVALUATION WINDOW
def run_2a():
    eval_days = np.arange((pd.Timestamp(EVAL_START) - START).days,
                          (pd.Timestamp(EVAL_END) - START).days + 1)
    eval_str = (START + pd.to_timedelta(eval_days, unit="D")).strftime("%Y-%m-%d").to_numpy()
    n_eval = len(eval_days)

    target_rows = []
    autonomy_rows = []
    for s in SCENARIOS:
        rules = scenario_dc_rules(s)
        D_nominal = np.array([nominal_autonomy_days(rules[dc]) for dc in pref])
        for r in SERVICE_TARGETS:
            tgt = np.zeros((n_eval, n_sku), dtype=int)
            win = np.zeros((n_eval, n_sku))
            cover = np.full((n_eval, n_sku), np.nan)   # autonomy days of the target
            daily = np.zeros((n_eval, n_sku))          # avg daily demand in the window
            for dc in DC_NAMES:
                idx = np.where(pref == dc)[0]
                if idx.size == 0 or dc not in rules:
                    continue
                rule = rules[dc]
                ev = booking_events(rule)
                for k, (b, d, d_next) in enumerate(ev):
                    b_next = ev[k + 1][0] if k + 1 < len(ev) else np.inf
                    on = (eval_days >= b) & (eval_days < b_next)
                    if not on.any():
                        continue
                    S, D = order_up_to(idx, b, d_next, rule["book_1800"], r, FC)
                    m, _, _ = window_demand(idx, b, d_next, rule["book_1800"], FC)
                    per_day = m / max(D, 1)
                    # Autonomy in days = target stock / average daily demand.
                    # Equals D at 50% with symmetric demand, more at higher robustness.
                    days_cover = np.where(per_day > 1e-9, S / np.maximum(per_day, 1e-9),
                                          np.nan)
                    tgt[np.ix_(on, idx)] = S
                    win[np.ix_(on, idx)] = D
                    cover[np.ix_(on, idx)] = days_cover
                    daily[np.ix_(on, idx)] = per_day
            target_rows.append(pd.DataFrame({
                "policy_id": f"A{int(r * 100)}", "scenario_id": s,
                "service_target": r, "sku_id": np.tile(skus, n_eval),
                "effective_day": np.repeat(eval_str, n_sku),
                "target_stock_units": tgt.ravel()}))
            autonomy_rows.append(pd.DataFrame({
                "scenario_id": s, "service_target": r, "sku_id": skus,
                "preferred_dc": pref,
                "served_by_dc": [rules[dc]["served_by"] for dc in pref],
                "autonomy_days_D": win.mean(axis=0),          # exact windows, averaged
                "autonomy_days_nominal": D_nominal,
                # Autonomy target in days at this robustness level
                "autonomy_days_target": nanmean_cols(cover),
                "avg_daily_demand": daily.mean(axis=0),
                "avg_target_units": tgt.mean(axis=0)}))

    targets = pd.concat(target_rows, ignore_index=True)
    autonomy = pd.concat(autonomy_rows, ignore_index=True)
    autonomy.to_csv("outputs/2a_autonomy_targets.csv", index=False)

    # WRITE ALTERNATIVE 
    for r in SERVICE_TARGETS:
        pid = f"A{int(r * 100)}"
        targets[targets.policy_id == pid].to_csv(
            f"outputs/ordering_alternative_{pid}.csv", index=False)
    print("Upload files: rows per alternative =",
          len(targets) // len(SERVICE_TARGETS))   # SKUs x eval days x 3 scenarios
    return autonomy


if __name__ == "__main__":
    run_2a()