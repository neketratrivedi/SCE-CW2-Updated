import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import nbinom, poisson

os.makedirs("outputs", exist_ok=True)
START = pd.Timestamp("2026-09-07")          # day 0 of the historical year
SCENARIOS = ["FAST", "MEDIUM", "SLOW"]
SERVICE_TARGETS = [0.50, 0.90, 0.99]
N_REPS = 5                                  # simulation replications
BASE_SEED = 20261020

# ---------------------------------------------------------------------
# 0. Data
# ---------------------------------------------------------------------
sku = pd.read_csv("QF_Facility_SKU_Master.csv").set_index("sku_id")
seq = pd.read_csv("QF_Facility_Supplier_Sequence.csv").set_index("sku_id")
scen = pd.read_csv("QF_Facility_Replenishment_Scenarios.csv")
params = pd.read_csv("QF_Facility_Design_Parameters.csv")
orders = pd.read_csv("QF_Facility_Orders.csv", usecols=["order_id", "day"])
lines = pd.read_csv("QF_Facility_Order_Lines.csv")

skus = sku.index.to_numpy()
n_sku = len(skus)
seq = seq.reindex(skus)

P_FULL = float(params.loc[params.parameter == "full_fill_probability", "value"].iloc[0])
P_PART = float(params.loc[params.parameter == "partial_fill_fraction", "value"].iloc[0])
print(f"Supply rule: full fill p={P_FULL}, partial fraction={P_PART}")

case = sku["case_pack_units"].to_numpy()
min_units = (sku["minimum_inbound_order_casepacks"] * sku["case_pack_units"]).to_numpy()
unit_vol = sku["unit_volume_l"].to_numpy()
opening = sku["opening_on_hand_units"].to_numpy().astype(float)
zone = sku["temperature_zone"].to_numpy()

# Actual daily demand per SKU in the historical year (days x SKUs)
lines = lines.merge(orders, on="order_id")
actual = (lines.pivot_table(index="day", columns="sku_id", values="quantity",
                            aggfunc="sum", fill_value=0)
          .reindex(index=range(365), columns=skus, fill_value=0)
          .to_numpy().astype(float))


# ---------------------------------------------------------------------
# 0b. Demand model (same as Task 1a): fitted here so this file runs alone
#     total units per day = exp(weekday + annual season + trend)
# ---------------------------------------------------------------------
import statsmodels.api as sm
import statsmodels.formula.api as smf

tot = pd.DataFrame({"t": np.arange(365), "demand": actual.sum(axis=1)})
tot["weekday"] = (START + pd.to_timedelta(tot["t"], unit="D")).dt.dayofweek
for k in (1, 2, 3):
    tot[f"s{k}"] = np.sin(2 * np.pi * k * tot["t"] / 365)
    tot[f"c{k}"] = np.cos(2 * np.pi * k * tot["t"] / 365)
model = smf.glm("demand ~ C(weekday) + s1 + c1 + s2 + c2 + s3 + c3 + t",
                data=tot, family=sm.families.Poisson()).fit(scale="X2")
coef = model.params

# Each SKU's share of total units, and its extra variability (alpha):
# variance = mu + alpha * mu^2 (negative binomial), method of moments
share = actual.sum(axis=0) / actual.sum()
mu_fit = np.outer(model.predict(tot), share)
alpha = np.clip(((actual - mu_fit) ** 2 - mu_fit).sum(axis=0)
                / (mu_fit ** 2).sum(axis=0), 0, None)

# ---------------------------------------------------------------------
# 1. Forecast from the demand model (any date)
#    total(t) = exp(b0 + weekday + Fourier season + trend); SKU = share x total
#    variance per SKU-day (negative binomial): mu + alpha * mu^2
# ---------------------------------------------------------------------
def forecast_total(dates):
    t = (dates - START).days.to_numpy()
    wd = dates.dayofweek.to_numpy()
    eta = coef["Intercept"] + coef["t"] * t
    for d in range(1, 7):
        eta = eta + coef[f"C(weekday)[T.{d}]"] * (wd == d)
    for k in (1, 2, 3):
        eta = (eta + coef[f"s{k}"] * np.sin(2 * np.pi * k * t / 365)
                   + coef[f"c{k}"] * np.cos(2 * np.pi * k * t / 365))
    return np.exp(eta)


def sku_mean_var(dates):
    tot = forecast_total(dates)
    mu = np.outer(tot, share)                   # days x SKUs
    var = mu + alpha[None, :] * mu ** 2
    return mu, var


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


# ---------------------------------------------------------------------
# 2. Delivery calendars, booking times and autonomy days per DC
# ---------------------------------------------------------------------
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
            "days": delivery_days(row, -60, 365 + 200),
            "offset": int(row["book_day_offset"]),
            "book_1800": row["book_time"] == "18:00",
            "interval": float(row["nominal_interval_days"]),
        }
    return rules


def autonomy_days(rule):
    """Autonomy D = booking lead + time to the delivery after next (nominal).
    Stock booked now must last until the following delivery arrives."""
    return int(np.ceil(rule["offset"] + rule["interval"]))


# ---------------------------------------------------------------------
# 3. Task 2a - target stock for the evaluation window (Part 1 upload)
#    target(t) = R-quantile of demand over the next D days, every day
# ---------------------------------------------------------------------
eval_dates = pd.date_range("2027-09-07", "2027-12-27", freq="D")
ext_dates = pd.date_range("2027-09-07", periods=len(eval_dates) + 60, freq="D")
mu_f, var_f = sku_mean_var(ext_dates)
cmu = np.vstack([np.zeros(n_sku), np.cumsum(mu_f, axis=0)])
cvar = np.vstack([np.zeros(n_sku), np.cumsum(var_f, axis=0)])

target_rows = []
autonomy_rows = []
for s in SCENARIOS:
    rules = scenario_dc_rules(s)
    D = np.array([autonomy_days(rules[dc]) for dc in seq["preferred_dc"]])
    for r in SERVICE_TARGETS:
        for i in range(len(eval_dates)):
            m = cmu[i + D, np.arange(n_sku)] - cmu[i, :]
            v = cvar[i + D, np.arange(n_sku)] - cvar[i, :]
            q = demand_quantile(m, v, r)
            target_rows.append(pd.DataFrame({
                "policy_id": f"A{int(r * 100)}", "scenario_id": s,
                "service_target": r, "sku_id": skus,
                "effective_day": eval_dates[i].strftime("%Y-%m-%d"),
                "target_stock_units": q}))
        autonomy_rows.append(pd.DataFrame({
            "scenario_id": s, "service_target": r, "sku_id": skus,
            "preferred_dc": seq["preferred_dc"].to_numpy(),
            "served_by_dc": [rules[dc]["served_by"] for dc in seq["preferred_dc"]],
            "autonomy_days_D": D}))

targets = pd.concat(target_rows, ignore_index=True)
autonomy = pd.concat(autonomy_rows, ignore_index=True)
avg_target = (targets.groupby(["scenario_id", "service_target", "sku_id"])
              ["target_stock_units"].mean().rename("avg_target_units").reset_index())
autonomy = autonomy.merge(avg_target, on=["scenario_id", "service_target", "sku_id"])
autonomy.to_csv("outputs/2a_autonomy_targets.csv", index=False)

# One upload CSV per alternative (one per service target, all three scenarios)
for r in SERVICE_TARGETS:
    pid = f"A{int(r * 100)}"
    targets[targets.policy_id == pid].to_csv(
        f"outputs/ordering_alternative_{pid}.csv", index=False)
print("Upload files: rows per alternative =",
      len(targets) // len(SERVICE_TARGETS))   # 2000 x 112 days x 3 scenarios

# ---------------------------------------------------------------------
# 4. Task 2b - simulation over the historical year
# ---------------------------------------------------------------------
hist_dates = START + pd.to_timedelta(np.arange(0, 365 + 120), unit="D")
mu_h, var_h = sku_mean_var(hist_dates)
cmu_h = np.vstack([np.zeros(n_sku), np.cumsum(mu_h, axis=0)])
cvar_h = np.vstack([np.zeros(n_sku), np.cumsum(var_h, axis=0)])

H = 365
dc_names = ["Local", "Regional", "National"]


def next_delivery(days, d):
    """First delivery day strictly after day d."""
    return days[np.searchsorted(days, d, side="right")]


def simulate(scenario, r, seed, demand=actual):
    rng = np.random.default_rng(seed)
    rules = scenario_dc_rules(scenario)
    pref = seq["preferred_dc"].to_numpy()
    nxt = {"second": seq["second_dc"].to_numpy(), "third": seq["third_dc"].to_numpy()}

    on_hand = opening.copy()
    arrivals = np.zeros((H + 200, n_sku))       # scheduled receipts by day
    pipeline = np.zeros(n_sku)                  # units ordered, not yet received

    # Booking events: (booking day, delivery day, next delivery) per DC
    bookings = {}
    pre_bookings = []
    for dc in dc_names:
        rule = rules[dc]
        for d in rule["days"]:
            b = d - rule["offset"]
            # Deliveries early in the year were booked before day 0: they are
            # placed before the first day (assumption: no artificial start-up gap).
            if d >= 0 and b < 0:
                pre_bookings.append((dc, d, next_delivery(rule["days"], d)))
            elif 0 <= b < H:
                bookings.setdefault(b, []).append((dc, d, next_delivery(rule["days"], d)))

    stats = {k: np.zeros(n_sku) for k in
             ["demand", "served", "lost", "stockout_days", "orders", "ordered_units",
              "partial_events", "supplier_lost_units", "sum_on_hand"]}
    max_on_hand = np.zeros(n_sku)

    def place(b, dc, d, d_next, at_1800):
        idx = np.where(pref == dc)[0]
        if idx.size == 0:
            return
        start = b + 1 if at_1800 else b              # demand not yet covered
        m = cmu_h[d_next, idx] - cmu_h[start, idx]
        v = cvar_h[d_next, idx] - cvar_h[start, idx]
        S = demand_quantile(m, v, r)                  # order-up-to level
        ip = on_hand[idx] + pipeline[idx]
        need = np.maximum(S - ip, 0)
        qty = np.ceil(need / case[idx]) * case[idx]
        qty = np.where((qty > 0) & (qty < min_units[idx]), min_units[idx], qty)
        sel = qty > 0
        idx, qty = idx[sel], qty[sel]
        if idx.size == 0:
            return
        stats["orders"][idx] += 1
        stats["ordered_units"][idx] += qty
        pipeline[idx] += qty
        # Supply rule: full with P_FULL, else P_PART ships and the rest goes
        # to the next DC in the sequence on that DC's next delivery day.
        remaining, day, chain = qty.copy(), np.full(idx.size, d), [None, "second", "third"]
        for level, key in enumerate(chain):
            if level > 0:
                dcs = nxt[key][idx]
                has = (remaining > 0) & pd.notna(dcs)
                lost_here = (remaining > 0) & ~has
                stats["supplier_lost_units"][idx[lost_here]] += remaining[lost_here]
                pipeline[idx[lost_here]] -= remaining[lost_here]
                remaining[~has] = 0
                for j in np.where(has)[0]:
                    days_dc = rules[dcs[j]]["days"]
                    day[j] = next_delivery(days_dc, day[j])
            active = remaining > 0
            if not active.any():
                break
            full = rng.random(idx.size) < P_FULL
            shipped = np.where(full, remaining, np.floor(remaining * P_PART))
            shipped = np.where(active, shipped, 0)
            stats["partial_events"][idx[active & ~full]] += 1
            for j in np.where(active)[0]:
                if day[j] < arrivals.shape[0]:
                    arrivals[day[j], idx[j]] += shipped[j]
            remaining = remaining - shipped
        # anything still remaining after the third DC is lost to the QF
        left = remaining > 0
        stats["supplier_lost_units"][idx[left]] += remaining[left]
        pipeline[idx[left]] -= remaining[left]

    for dc, d, d_next in pre_bookings:              # booked before day 0
        place(0, dc, d, d_next, False)

    for t in range(H):
        on_hand += arrivals[t]                       # on the shelves at 06:00
        pipeline -= arrivals[t]
        for dc, d, d_next in bookings.get(t, []):
            if not rules[dc]["book_1800"]:           # 08:00 booking
                place(t, dc, d, d_next, False)
        dem = demand[t]
        served = np.minimum(on_hand, dem)
        on_hand -= served
        stats["demand"] += dem
        stats["served"] += served
        stats["lost"] += dem - served
        stats["stockout_days"] += (dem > served)
        for dc, d, d_next in bookings.get(t, []):
            if rules[dc]["book_1800"]:               # 18:00 booking, after trading
                place(t, dc, d, d_next, True)
        stats["sum_on_hand"] += on_hand
        max_on_hand = np.maximum(max_on_hand, on_hand)

    out = pd.DataFrame(stats, index=skus)
    out["avg_on_hand_units"] = out.pop("sum_on_hand") / H
    out["max_on_hand_units"] = max_on_hand
    out["avg_volume_l"] = out["avg_on_hand_units"] * unit_vol
    out["max_volume_l"] = max_on_hand * unit_vol
    out["zone"] = zone
    out["preferred_dc"] = seq["preferred_dc"].to_numpy()
    out["scenario_id"], out["service_target"], out["seed"] = scenario, r, seed
    return out


results = []
for s in SCENARIOS:
    for r in SERVICE_TARGETS:
        for rep in range(N_REPS):
            res = simulate(s, r, BASE_SEED + rep)   # same seeds across policies
            res["rep"] = rep
            results.append(res)
        print(f"simulated {s} {r}")
sim = pd.concat(results).rename_axis("sku_id").reset_index()
sim.to_csv("outputs/2b_simulation_by_sku.csv", index=False)

# ---------------------------------------------------------------------
# 5. Task 2c - comparison
# ---------------------------------------------------------------------
per_rep = (sim.groupby(["scenario_id", "service_target", "rep"])
           .agg(demand=("demand", "sum"), served=("served", "sum"),
                lost=("lost", "sum"), orders=("orders", "sum"),
                ordered_units=("ordered_units", "sum"),
                avg_on_hand=("avg_on_hand_units", "sum"),
                avg_volume_l=("avg_volume_l", "sum"),
                peak_volume_l=("max_volume_l", "sum"),
                stockout_days=("stockout_days", "sum"),
                partial_events=("partial_events", "sum"),
                supplier_lost=("supplier_lost_units", "sum"))
           .reset_index())
per_rep["inventory_service"] = per_rep["served"] / per_rep["demand"]

summary = per_rep.groupby(["scenario_id", "service_target"]).agg(
    inventory_service=("inventory_service", "mean"),
    service_sd=("inventory_service", "std"),
    lost_units=("lost", "mean"),
    supplier_orders=("orders", "mean"),
    avg_order_units=("ordered_units", "mean"),
    avg_on_hand_units=("avg_on_hand", "mean"),
    avg_volume_m3=("avg_volume_l", lambda x: x.mean() / 1000),
    sum_of_peak_volume_m3=("peak_volume_l", lambda x: x.mean() / 1000),
    stockout_sku_days=("stockout_days", "mean"),
    partial_fill_events=("partial_events", "mean"),
).reset_index()
summary["avg_order_units"] = summary["avg_order_units"] / summary["supplier_orders"]
summary["service_ci95"] = 1.96 * summary.pop("service_sd") / np.sqrt(N_REPS)
summary = summary.merge(
    autonomy.groupby(["scenario_id", "service_target"])
    .agg(avg_autonomy_days=("autonomy_days_D", "mean"),
         avg_target_units=("avg_target_units", "mean")).reset_index(),
    on=["scenario_id", "service_target"])
print(summary.round(4).to_string())
summary.to_csv("outputs/2c_comparison_summary.csv", index=False)

by_zone = (sim.groupby(["scenario_id", "service_target", "zone"])
           .agg(demand=("demand", "sum"), served=("served", "sum"),
                avg_volume_l=("avg_volume_l", "sum"))
           .reset_index())
by_zone["inventory_service"] = by_zone["served"] / by_zone["demand"]
by_zone["avg_volume_m3"] = by_zone["avg_volume_l"] / N_REPS / 1000
print(by_zone[["scenario_id", "service_target", "zone", "inventory_service",
               "avg_volume_m3"]].round(3).to_string())
by_zone.to_csv("outputs/2c_comparison_by_zone.csv", index=False)

# Chart: service vs stock volume for every alternative
fig, ax = plt.subplots(figsize=(7, 4.5))
for s, mk in zip(SCENARIOS, ["o", "s", "^"]):
    d = summary[summary.scenario_id == s]
    ax.plot(d["avg_volume_m3"], d["inventory_service"] * 100, marker=mk, label=s)
    for _, row in d.iterrows():
        ax.annotate(f"{int(row.service_target * 100)}%",
                    (row.avg_volume_m3, row.inventory_service * 100),
                    textcoords="offset points", xytext=(5, -10), fontsize=8)
ax.set_xlabel("Average stock volume held (m³)")
ax.set_ylabel("Inventory service (% of units supplied)")
ax.set_title("Service vs stock held, by resupply scenario and service target")
ax.legend()
plt.tight_layout()
plt.savefig("outputs/2c_service_vs_volume.png", dpi=150)
plt.show()
