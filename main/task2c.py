"""Task 2c - comparison of the alternatives (tables and chart).
Standalone: reads the 2a and 2b outputs from the outputs folder."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from task2a import SCENARIOS, N_REPS, SIM_MODE


#COMPARISON
def run_2c(sim, autonomy):
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
        total_ordered_units=("ordered_units", "mean"),               # NEW: per year
        supplier_lost_units=("supplier_lost", "mean"),               # NEW
    ).reset_index()
    summary["avg_order_units"] = summary["avg_order_units"] / summary["supplier_orders"]
    summary["service_ci95"] = 1.96 * summary.pop("service_sd") / np.sqrt(N_REPS)
    # NEW: inbound frequency per product, and exposure to unfillable supplier orders
    summary["orders_per_sku_per_year"] = summary["supplier_orders"] / sim["sku_id"].nunique()
    summary["unfillable_share"] = (summary["supplier_lost_units"]
                                   / summary["total_ordered_units"])
    summary = summary.merge(
        autonomy.groupby(["scenario_id", "service_target"])
        .agg(avg_autonomy_days=("autonomy_days_D", "mean"),
             avg_autonomy_days_nominal=("autonomy_days_nominal", "mean"),
             avg_autonomy_days_target=("autonomy_days_target", "mean"),   # NEW
             avg_target_units=("avg_target_units", "mean"),
             sum_target_units=("avg_target_units", "sum"),
             sum_daily_demand=("avg_daily_demand", "sum")).reset_index(),
        on=["scenario_id", "service_target"])
    # NEW: demand-weighted autonomy = total target stock / total daily demand.
    # The plain SKU average above is pulled up by slow movers (1 unit held for
    # 0.03 units/day = 33 days); the weighted one reflects where the stock is.
    summary["weighted_autonomy_days_target"] = (summary.pop("sum_target_units")
                                                / summary.pop("sum_daily_demand"))
    summary["sim_mode"] = SIM_MODE
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
    ax.set_title(f"Service vs stock held ({SIM_MODE} year)")
    ax.legend()
    plt.tight_layout()
    plt.savefig("outputs/2c_service_vs_volume.png", dpi=150)
    plt.show()



if __name__ == "__main__":
    run_2c(pd.read_csv("outputs/2b_simulation_by_sku.csv"),
           pd.read_csv("outputs/2a_autonomy_targets.csv"))