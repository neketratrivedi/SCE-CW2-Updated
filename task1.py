import os #added for compatibility with computer folders
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm
import statsmodels.formula.api as smf
os.makedirs("outputs", exist_ok=True)
from itertools import combinations

# dictionaries

weekday_names = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday"
}


df_sku = pd.read_csv("QF_Facility_SKU_Master.csv")
df_lines = pd.read_csv("QF_Facility_Order_Lines.csv")
df_order = pd.read_csv("QF_Facility_Orders.csv")

# 1. Prepare order dates
df_order["placement_timestamp"] = pd.to_datetime(
    df_order["placement_timestamp"]
)

df_order["order_date"] = (
    df_order["placement_timestamp"].dt.normalize()
)
df_order["weekday"] = df_order["placement_timestamp"].dt.dayofweek
df_order["hour"] = df_order["placement_timestamp"].dt.hour

# 2. Attach dates to order lines
df_order_sku = df_lines.merge(
    df_order[["order_id", "order_date", "hour"]],
    on="order_id",
    how="left",
    validate="many_to_one"
)
# # 3–4 (revised). Daily demand per SKU, every date × every SKU, zeros filled
# dates = pd.date_range(df_order["order_date"].min(),
#                       df_order["order_date"].max(), freq="D")
# sku_ids = df_sku["sku_id"].dropna().unique()
#
# daily_totals = (
#     df_order_sku.groupby(["order_date", "sku_id"])["quantity"].sum()
#     .reindex(pd.MultiIndex.from_product([dates, sku_ids],
#              names=["order_date", "sku_id"]), fill_value=0)
#     .rename("demand").reset_index()
# )
#This code gives demand per day rather than per hour, because stock replenishment happens overnight and it also reduces the number of row entries to around 750,000 as opposed to that times 24. Code would process faster. Also takes care of the broken timestamp issue. (after day 56, every order is stamped in at midnight so thats a bug that this code surpasses)
# 3. Aggregate demand by SKU and date
daily_demand = (
    df_order_sku
    .groupby(["order_date", "sku_id", "hour"], as_index=False)["quantity"]
    .sum()
    .rename(columns={"quantity": "demand"})
)

# 4. Include every date and every SKU, including zero-demand days
dates = pd.date_range(
    df_order["order_date"].min(),
    df_order["order_date"].max(),
    freq="D"
)

# Use the master file to include all SKUs in the assortment
sku_ids = df_sku["sku_id"].dropna().unique()
hours = range(24)

full_index = pd.MultiIndex.from_product(
    [dates, sku_ids, hours],
    names=["order_date", "sku_id", "hour"]
)

daily_demand = (
    daily_demand
    .set_index(["order_date", "sku_id", "hour"])
    .reindex(full_index, fill_value=0)
    .reset_index()
    .sort_values(["sku_id", "order_date", "hour"])
)

# 5. Product-level descriptive statistics
daily_totals = (
    daily_demand
    .groupby(["order_date", "sku_id"], as_index=False)["demand"]
    .sum()
)

product_stats = (
    daily_totals.groupby("sku_id")["demand"]
    .agg(
        mean_daily="mean",
        std_daily="std",
        variance="var",
        zero_demand_share=lambda x: (x == 0).mean()
    )
)

product_stats["cv"] = (
    product_stats["std_daily"]
    / product_stats["mean_daily"].replace(0, np.nan)
)

# 6. Add calendar features
daily_demand["weekday"] = daily_demand["order_date"].dt.dayofweek
daily_demand["month"] = daily_demand["order_date"].dt.month
daily_demand["year"] = daily_demand["order_date"].dt.year



# 7. Average demand by weekday, for each SKU
df_days = (
    daily_demand.groupby(["sku_id", "weekday"])["demand"]
    .mean()
    .reset_index(name="mean_demand")
)

# 8. Average demand by calendar month, for each SKU
df_month = (
    daily_demand.groupby(["sku_id", "month"])["demand"]
    .mean()
    .reset_index(name="mean_demand")
)

# 9. Average demand by year, for each SKU
df_year = (
    daily_demand.groupby(["sku_id", "year"])["demand"]
    .mean()
    .reset_index(name="mean_demand")
)

print(product_stats.head())
print(df_days.head())
print(df_month.head())
print(df_year.head())

# Compare weekday demand against each SKU's overall mean

weekday_seasonality = df_days.merge(
    product_stats[["mean_daily"]],
    on="sku_id",
    how="left"
)

weekday_seasonality["relative_demand"] = (
    weekday_seasonality["mean_demand"]
    / weekday_seasonality["mean_daily"].replace(0, np.nan)
)

weekday_seasonality["weekday_name"] = (
    weekday_seasonality["weekday"]
    .map(weekday_names)
)

print(weekday_seasonality)

# Compare weekday demand against each SKU's overall mean

monthly_seasonality = df_month.merge(
    product_stats[["mean_daily"]],
    on="sku_id",
    how="left"
)

monthly_seasonality["relative_demand"] = (
    monthly_seasonality["mean_demand"]
    / monthly_seasonality["mean_daily"].replace(0, np.nan)
)

monthly_seasonality["month_name"] = (
    monthly_seasonality["month"]
    .map({
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December"
    })
)

print(monthly_seasonality)


# trend over time

daily_demand["quarter"] = (
    daily_demand["order_date"].dt.to_period("Q").astype(str)
)

df_quarter = (
    daily_demand.groupby(["sku_id", "quarter"])["demand"]
    .mean()
    .reset_index(name="mean_demand")
)

print(df_quarter)

# analyze orders by day of week and time of day; identify peak days and periods.
# no sku, just time analysis

print(daily_demand.head())

demand_per_day = (
    daily_demand
    .groupby(["weekday"], as_index=False)["demand"]
    .sum()
)


demand_per_hour = (
    daily_demand
    .groupby(["hour"], as_index=False)["demand"]
    .sum()
)


max_demand_day = demand_per_day.loc[demand_per_day["demand"].idxmax()]
max_demand_hour = demand_per_hour.loc[demand_per_hour["demand"].idxmax()]

print(f"Peak demand day: {max_demand_day['weekday']} with demand {max_demand_day['demand']}")
print(f"Peak demand hour: {max_demand_hour['hour']} with demand {max_demand_hour['demand']}")


# peak analysis

df_order["weekday_name"] = df_order["weekday"].map(weekday_names)

daily_orders = (
    df_order.groupby(["placement_timestamp"])
    .size()
)

orders_by_date = df_order.assign(
    order_date=df_order["placement_timestamp"].dt.normalize()
)

daily_counts = (
    orders_by_date.groupby(["order_date", "weekday", "weekday_name"])
    .size()
    .reset_index(name="orders")
)

peak_days = (
    daily_counts.groupby(["weekday", "weekday_name"])["orders"]
    .agg(["mean", "median", "max"])
    .reset_index()
    .sort_values("weekday")
)

print(peak_days)

peak_days.plot(
    x="weekday_name",
    y="mean",
    kind="bar",
    legend=False,
    xlabel="Day of week",
    ylabel="Average orders per day",
    title="Average Daily Orders by Weekday"
)
plt.tight_layout()
plt.show()


hourly_counts = (
    df_order.groupby(["order_date", "hour"])
    .size()
    .reset_index(name="orders")
)

peak_hours = (
    hourly_counts.groupby("hour")["orders"]
    .mean()
    .reindex(range(24), fill_value=0)
    .reset_index(name="mean_orders")
)

print(peak_hours.sort_values("mean_orders", ascending=False))

peak_hours.plot(
    x="hour",
    y="mean_orders",
    kind="bar",
    legend=False,
    xlabel="Hour of day",
    ylabel="Average orders per hour",
    title="Average Hourly Order Volume"
)
plt.tight_layout()
plt.show()

df_order["period"] = pd.cut(
    df_order["hour"],
    bins=[-1, 5, 11, 17, 23],
    labels=["Night (00–05)", "Morning (06–11)",
            "Afternoon (12–17)", "Evening (18–23)"]
)

period_counts = (
    df_order.groupby(
        ["order_date", "period"], observed=False
    )
    .size()
    .reset_index(name="orders")
)

peak_periods = (
    period_counts.groupby("period", observed=False)["orders"]
    .agg(["mean", "median", "max"])
    .reset_index()
)

print(peak_periods)

weekday_hour = (
    df_order.groupby(["weekday_name", "hour"])
    .size()
    .reset_index(name="total_orders")
)

# Average orders per hour for each weekday,
# accounting for how many dates of each weekday are observed
dates_per_weekday = (
    df_order[["order_date", "weekday_name"]]
    .drop_duplicates()
    .groupby("weekday_name")
    .size()
)

weekday_hour["mean_orders_per_hour"] = (
    weekday_hour["total_orders"]
    / weekday_hour["weekday_name"].map(dates_per_weekday)
)

print(
    weekday_hour.sort_values(
        "mean_orders_per_hour", ascending=False
    ).head(10)
)

# basket-size distributions

basket_stats = df_order["basket_size_units"].describe(
    percentiles=[0.25, 0.50, 0.75, 0.90, 0.99]
)

print(basket_stats)

basket_distribution = (
    df_order["basket_size_units"]
    .value_counts()
    .sort_index()
    .rename_axis("basket_size_units")
    .reset_index(name="number_of_orders")
)

basket_distribution["percentage"] = (
    basket_distribution["number_of_orders"]
    / len(df_order) * 100
)

print(basket_distribution)

basket_distribution.plot(
    x="basket_size_units",
    y="percentage",
    kind="bar",
    legend=False,
    xlabel="Number of units per basket",
    ylabel="Orders (%)",
    title="Distribution of Basket Sizes"
)

plt.tight_layout()
plt.show()

# products ordered together 

basket_skus = (
    df_lines.groupby("order_id")["sku_id"]
    .apply(lambda x: sorted(set(x.dropna())))
)

n_orders = df_lines["order_id"].nunique()

pair_counts = {}

for skus in basket_skus:
    for sku_a, sku_b in combinations(skus, 2):
        pair_counts[(sku_a, sku_b)] = (pair_counts.get((sku_a, sku_b), 0) + 1)

frequent_pairs = pd.DataFrame(
    [
        {
            "sku_a": pair[0],
            "sku_b": pair[1],
            "orders_together": count,
            "perc of orders together over total orders": 100 * count / n_orders
        }
        for pair, count in pair_counts.items()
    ]
)

frequent_pairs = frequent_pairs.sort_values("orders_together", ascending=False)

# print(frequent_pairs.head(20))

sku_order_counts = (
    df_lines.groupby("sku_id")["order_id"]
    .nunique()
)

frequent_pairs["support"] = (
    frequent_pairs["orders_together"] / n_orders
)

frequent_pairs["confidence_a_to_b"] = (
    frequent_pairs["orders_together"]
    / frequent_pairs["sku_a"].map(sku_order_counts)
)

frequent_pairs["confidence_b_to_a"] = (
    frequent_pairs["orders_together"]
    / frequent_pairs["sku_b"].map(sku_order_counts)
)

frequent_pairs["lift"] = (
    frequent_pairs["orders_together"] * n_orders
    / (
        frequent_pairs["sku_a"].map(sku_order_counts)
        * frequent_pairs["sku_b"].map(sku_order_counts)
    )
)

results = frequent_pairs.sort_values("lift", ascending=False).head(20)
print(results)
# =====================================================================
# 1e. TEMPERATURE-ZONE COMBINATIONS
# =====================================================================

# Lines per order (number of different products in each order)
lines_per_order = df_lines.groupby("order_id").size().rename("lines")
df_order = df_order.merge(lines_per_order, left_on="order_id",
                          right_index=True, how="left")

# Zone combination of each order, e.g. "Ambient + Chilled"
order_zones = (
    df_lines.groupby("order_id")["temperature_zone"]
    .agg(lambda z: " + ".join(sorted(set(z))))
    .rename("zone_combo")
)
df_order = df_order.merge(order_zones, left_on="order_id",
                          right_index=True, how="left")
df_order["n_zones"] = df_order["zone_combo"].str.count(r"\+") + 1

# Share of orders per zone combination
zone_mix = (df_order["zone_combo"].value_counts(normalize=True)
            .mul(100).round(2).rename("pct_orders").reset_index())
print("\nShare of orders by zone combination (%):")
print(zone_mix)

# Share of orders spanning 1, 2 or 3 zones
print("\nShare of orders by number of zones (%):")
print(df_order["n_zones"].value_counts(normalize=True).sort_index()
      .mul(100).round(2))

# Probability that each zone appears in an order
print("\nProbability each zone appears in an order:")
for z in ["Ambient", "Chilled", "Frozen"]:
    share = df_order["zone_combo"].str.contains(z).mean() * 100
    print(f"  P({z} in order) = {share:.1f}%")

# How the number of zones changes with basket size (lines per order)
zones_by_size = pd.crosstab(
    pd.cut(df_order["lines"], bins=[0, 1, 2, 3, 5, 8, 25]),
    df_order["n_zones"], normalize="index"
).mul(100).round(1)
print("\nNumber of zones by basket size (row %):")
print(zones_by_size)

# Average lines per zone, when that zone is in the order
lines_per_zone = (df_lines.groupby(["order_id", "temperature_zone"]).size()
                  .groupby("temperature_zone").mean().round(2))
print("\nAverage lines per zone (given the zone is in the order):")
print(lines_per_zone)

zone_mix.plot(x="zone_combo", y="pct_orders", kind="barh", legend=False,
              xlabel="Orders (%)", ylabel="",
              title="Temperature-zone mix per order")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("outputs/1e_zone_mix.png", dpi=150)
plt.show()

zone_mix.to_csv("outputs/1e_zone_mix.csv", index=False)
zones_by_size.to_csv("outputs/1e_zones_by_basket_size.csv")
lines_per_zone.to_csv("outputs/1e_lines_per_zone.csv")

# =====================================================================
# 1f. ORDER-TO-STAGING (OTS) TIME BUDGET
# =====================================================================
# Rule 5 of the brief: latest staged time = placement + promise - est. delivery
# so the OTS budget (minutes) = promise - estimated_delivery_minutes

promises = [20, 30, 45]
for p in promises:
    df_order[f"ots_budget_{p}"] = p - df_order["estimated_delivery_minutes"]

ots_cols = [f"ots_budget_{p}" for p in promises]
ots_summary = df_order[ots_cols].describe(
    percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).T.round(2)
print("\nOTS budget by promise (minutes):")
print(ots_summary)

# Share of orders whose budget falls inside each OTS scenario range (v2 brief)
ots_ranges = {"Fast": (4, 5), "Medium": (5, 7), "Slow": (8, 10)}
rows = []
for p in promises:
    b = df_order[f"ots_budget_{p}"]
    for name, (lo, hi) in ots_ranges.items():
        rows.append({"promise_min": p, "ots_scenario": name,
                     "range_min": f"{lo}-{hi}",
                     "pct_orders_in_range": round(100 * b.between(lo, hi).mean(), 2)})
ots_fit = pd.DataFrame(rows)
print("\nShare of orders inside each OTS scenario range:")
print(ots_fit)

fig, ax = plt.subplots(figsize=(8, 4.5))
for p in promises:
    ax.hist(df_order[f"ots_budget_{p}"], bins=60, alpha=0.5,
            label=f"{p}-min promise")
for name, (lo, hi) in ots_ranges.items():
    ax.axvspan(lo, hi, alpha=0.12)
    ax.text((lo + hi) / 2, ax.get_ylim()[1] * 0.95, name,
            ha="center", va="top", fontsize=8)
ax.set_xlabel("OTS budget (minutes)")
ax.set_ylabel("Orders")
ax.set_title("Order-to-staging time budget by delivery promise")
ax.legend()
plt.tight_layout()
plt.savefig("outputs/1f_ots_budget.png", dpi=150)
plt.show()

ots_summary.to_csv("outputs/1f_ots_budget_summary.csv")
ots_fit.to_csv("outputs/1f_ots_scenario_fit.csv", index=False)
df_order[["order_id", "day", "placement_date", "placement_minute",
          "lines", "zone_combo", "n_zones", "estimated_delivery_minutes",
          "courier_arrival_offset_minutes"] + ots_cols].to_csv(
    "outputs/1ef_order_features.csv", index=False)
print("\nSaved 1e and 1f outputs to the outputs/ folder.")
