"""Task 2b - simulation of every scenario x service target."""
import numpy as np
import pandas as pd

from task2a import (START, SCENARIOS, SERVICE_TARGETS, N_REPS, BASE_SEED, H,
                    FC_FIRST, T_MAX, DC_NAMES, SIM_MODE, seq, n_sku, skus, pref,
                    P_FULL, P_PART, case, min_units, unit_vol, opening, zone,
                    FC, HIST, sample_demand, scenario_dc_rules, booking_events,
                    order_up_to)
if SIM_MODE == "historical":
    from task2a import actual

#SIMULATION
SIM_FIRST = 0 if SIM_MODE == "historical" else FC_FIRST   # first simulated day index
SIM_CUM = HIST if SIM_MODE == "historical" else FC        # what the policy plans with


def simulate(scenario, r, seed, demand):
    """demand: H x SKUs units demanded, row 0 = day SIM_FIRST."""
    rng = np.random.default_rng(seed)
    rules = scenario_dc_rules(scenario)
    nxt = {"second": seq["second_dc"].to_numpy(), "third": seq["third_dc"].to_numpy()}

    def next_delivery(days, d):
        """First delivery day strictly after day d."""
        return days[np.searchsorted(days, d, side="right")]

    on_hand = opening.copy()
    arrivals = np.zeros((T_MAX + 1, n_sku))      # scheduled receipts by day index
    pipeline = np.zeros(n_sku)                   # units ordered, not yet received
    sim_end = SIM_FIRST + H

    # BOOKING EVENTS
    bookings = {}
    pre_bookings = []
    for dc in DC_NAMES:
        if dc not in rules:
            continue
        for b, d, d_next in booking_events(rules[dc]):
            # Deliveries early in the period were booked before it started: they
            # are placed on the first day (assumption: no artificial start-up gap).
            if d >= SIM_FIRST and b < SIM_FIRST:
                pre_bookings.append((dc, d, d_next))
            elif SIM_FIRST <= b < sim_end:
                bookings.setdefault(b, []).append((dc, d, d_next))

    stats = {k: np.zeros(n_sku) for k in
             ["demand", "served", "lost", "stockout_days", "orders", "ordered_units",
              "partial_events", "supplier_lost_units", "sum_on_hand"]}
    max_on_hand = np.zeros(n_sku)

    def place(b, dc, d, d_next, at_1800):
        idx = np.where(pref == dc)[0]
        if idx.size == 0:
            return
        S, _ = order_up_to(idx, b, d_next, at_1800, r, SIM_CUM)   # same rule as 2a
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

    for dc, d, d_next in pre_bookings:              # booked before the start
        place(SIM_FIRST, dc, d, d_next, False)

    for t in range(SIM_FIRST, sim_end):
        on_hand += arrivals[t]                       # on the shelves at 06:00
        pipeline -= arrivals[t]
        for dc, d, d_next in bookings.get(t, []):
            if not rules[dc]["book_1800"]:           # 08:00 booking
                place(t, dc, d, d_next, False)
        dem = demand[t - SIM_FIRST]
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
    out["preferred_dc"] = pref
    out["scenario_id"], out["service_target"], out["seed"] = scenario, r, seed
    return out

def run_2b():
    """Run all replications, write the per-SKU results and return them."""
    print(f"Simulating {SIM_MODE} year: "
          f"{(START + pd.Timedelta(days=SIM_FIRST)).date()} + {H} days")
    results = []
    for rep in range(N_REPS):
        # Same demand for every policy within a replication (common random numbers)
        demand = actual if SIM_MODE == "historical" else sample_demand(BASE_SEED + 1000 + rep)
        for s in SCENARIOS:
            for r in SERVICE_TARGETS:
                res = simulate(s, r, BASE_SEED + rep, demand)   # same seeds across policies
                res["rep"] = rep
                results.append(res)
        print(f"simulated replication {rep + 1}/{N_REPS}")
    sim = pd.concat(results).rename_axis("sku_id").reset_index()
    sim.to_csv("outputs/2b_simulation_by_sku.csv", index=False)
    return sim


if __name__ == "__main__":
    run_2b()