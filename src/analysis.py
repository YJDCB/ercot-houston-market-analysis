"""Produce descriptive ERCOT market analysis tables and six research figures.

This is an observational analysis.  The charts identify market conditions that
coincide with high prices; they do not claim that one variable causes prices.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "ercot_market.sqlite"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "figures"
PRICE = "dam_price_usd_mwh"
COLORS = {
    "natural_gas_mw": "#d95f02",
    "wind_mw": "#1b9e77",
    "solar_mw": "#e6ab02",
    "coal_mw": "#7570b3",
    "nuclear_mw": "#666666",
}


def query_market() -> pd.DataFrame:
    with sqlite3.connect(DATABASE) as connection:
        return pd.read_sql_query(
            "SELECT * FROM market_features ORDER BY timestamp", connection, parse_dates=["timestamp"]
        )


def percentile(series: pd.Series, quantile: float) -> float:
    return series.quantile(quantile, interpolation="linear")


def annual_summary(data: pd.DataFrame) -> pd.DataFrame:
    grouped = data.groupby("year")
    result = grouped.agg(
        observations=(PRICE, "size"),
        average_load_mw=("system_load_mw", "mean"),
        peak_load_mw=("system_load_mw", "max"),
        average_natural_gas_mw=("natural_gas_mw", "mean"),
        average_wind_mw=("wind_mw", "mean"),
        average_solar_mw=("solar_mw", "mean"),
        average_coal_mw=("coal_mw", "mean"),
        average_nuclear_mw=("nuclear_mw", "mean"),
        average_biomass_mw=("biomass_mw", "mean"),
        average_hydro_mw=("hydro_mw", "mean"),
        average_other_mw=("other_mw", "mean"),
        mean_price_usd_mwh=(PRICE, "mean"),
        median_price_usd_mwh=(PRICE, "median"),
    )
    for q, label in [(0.25, "p25"), (0.75, "p75"), (0.95, "p95"), (0.99, "p99")]:
        result[f"{label}_price_usd_mwh"] = grouped[PRICE].apply(lambda values, q=q: percentile(values, q))
    result["average_other_generation_mw"] = (
        result["average_biomass_mw"] + result["average_hydro_mw"] + result["average_other_mw"]
    )
    return result.reset_index()


def make_figures(data: pd.DataFrame, annual: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    years = annual["year"].tolist()
    plt.style.use("seaborn-v0_8-whitegrid")

    # 1. Load and generation mix evolution
    figure, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(years, annual["average_load_mw"], marker="o", label="Average load")
    axes[0].plot(years, annual["peak_load_mw"], marker="o", label="Peak load")
    axes[0].set_title("ERCOT load evolution")
    axes[0].set_ylabel("MW")
    axes[0].legend(frameon=False)
    bottom = np.zeros(len(annual))
    fuel_columns = ["natural_gas_mw", "wind_mw", "solar_mw", "coal_mw", "nuclear_mw", "other_generation_mw"]
    fuel_labels = ["Natural gas", "Wind", "Solar", "Coal", "Nuclear", "Other generation"]
    for column, label in zip(fuel_columns, fuel_labels):
        values = annual[f"average_{column}"]
        axes[1].bar(years, values, bottom=bottom, label=label, color=COLORS.get(column, "#8c8c8c"))
        bottom += values.to_numpy()
    axes[1].set_title("Average generation mix")
    axes[1].set_ylabel("Average MW")
    axes[1].legend(frameon=False, fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "market_evolution.png", dpi=180)
    plt.close(figure)

    # 2. Price distribution by year: retain tails in a boxplot and mark P95.
    samples = [data.loc[data["year"].eq(year), PRICE].to_numpy() for year in years]
    figure, axis = plt.subplots(figsize=(11, 5))
    axis.boxplot(samples, tick_labels=years, showfliers=False, whis=(5, 95), patch_artist=True,
                 boxprops={"facecolor": "#9ecae1"}, medianprops={"color": "#08519c", "linewidth": 2})
    axis.plot(range(1, len(years) + 1), annual["p95_price_usd_mwh"], marker="o", color="#d7301f", label="Annual P95")
    axis.set_title("HB_HOUSTON day-ahead price distribution by year")
    axis.set_xlabel("Year")
    axis.set_ylabel("USD/MWh")
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "price_distribution_by_year.png", dpi=180)
    plt.close(figure)

    # 3. Load bins show conditional price distributions without overplotting.
    bins = pd.qcut(data["system_load_mw"], q=20, duplicates="drop")
    load_bins = data.assign(load_bin=bins).groupby("load_bin", observed=True).agg(
        mean_load_mw=("system_load_mw", "mean"), mean_price=(PRICE, "mean"), median_price=(PRICE, "median")
    )
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(load_bins["mean_load_mw"], load_bins["median_price"], marker="o", label="Median price")
    axis.plot(load_bins["mean_load_mw"], load_bins["mean_price"], marker="o", label="Mean price")
    axis.set_title("Houston day-ahead price by ERCOT system-load bin")
    axis.set_xlabel("Average system load within bin (MW)")
    axis.set_ylabel("USD/MWh")
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "price_vs_load.png", dpi=180)
    plt.close(figure)

    # 4. Solar growth and the intraday price profile.
    hourly = data.groupby(["year", "hour_of_day"], as_index=False)[PRICE].mean()
    figure, axis = plt.subplots(figsize=(11, 5))
    for year in years:
        portion = hourly.loc[hourly["year"].eq(year)]
        axis.plot(portion["hour_of_day"], portion[PRICE], label=str(year))
    axis.set_title("Average HB_HOUSTON price by hour of day")
    axis.set_xlabel("Hour beginning (Central time)")
    axis.set_ylabel("USD/MWh")
    axis.set_xticks(range(0, 24, 2))
    axis.legend(title="Year", frameon=False, ncol=3)
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "hourly_price_profile_by_year.png", dpi=180)
    plt.close(figure)

    # 5. Joint relative load and renewable conditions.
    order_load = ["Low load", "Medium load", "High load", "Extreme load"]
    order_renewable = ["Low renewable", "Medium renewable", "High renewable"]
    joint = data.pivot_table(index="renewable_regime", columns="load_regime", values=PRICE, aggfunc="median")
    joint = joint.reindex(index=order_renewable, columns=order_load)
    figure, axis = plt.subplots(figsize=(9, 4.5))
    image = axis.imshow(joint, cmap="YlOrRd", aspect="auto")
    axis.set_xticks(range(len(order_load)), order_load)
    axis.set_yticks(range(len(order_renewable)), order_renewable)
    for row in range(joint.shape[0]):
        for column in range(joint.shape[1]):
            axis.text(column, row, f"${joint.iloc[row, column]:.1f}", ha="center", va="center")
    axis.set_title("Median price under load × renewable regimes")
    colorbar = figure.colorbar(image, ax=axis)
    colorbar.set_label("Median USD/MWh")
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "price_by_market_regime.png", dpi=180)
    plt.close(figure)

    # 6. Spike rates: the core risk-oriented descriptive result.
    spike = data.groupby(["load_regime", "renewable_regime"], as_index=False).agg(
        spike_rate=("price_spike_p95", "mean"), observations=("price_spike_p95", "size")
    )
    pivot = spike.pivot(index="renewable_regime", columns="load_regime", values="spike_rate").reindex(
        index=order_renewable, columns=order_load
    )
    figure, axis = plt.subplots(figsize=(9, 4.5))
    image = axis.imshow(pivot, cmap="Reds", aspect="auto", vmin=0)
    axis.set_xticks(range(len(order_load)), order_load)
    axis.set_yticks(range(len(order_renewable)), order_renewable)
    for row in range(pivot.shape[0]):
        for column in range(pivot.shape[1]):
            axis.text(column, row, f"{pivot.iloc[row, column]:.1%}", ha="center", va="center")
    axis.set_title("P95 price-spike rate by market regime")
    colorbar = figure.colorbar(image, ax=axis)
    colorbar.set_label("Spike rate")
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "spike_rate_by_market_regime.png", dpi=180)
    plt.close(figure)


def write_tables(data: pd.DataFrame, annual: pd.DataFrame) -> None:
    annual.to_csv(PROCESSED_DIR / "annual_market_summary.csv", index=False)
    data.groupby("year")[PRICE].describe(percentiles=[0.25, 0.75, 0.95, 0.99]).reset_index().to_csv(
        PROCESSED_DIR / "price_distribution_by_year.csv", index=False
    )
    data.groupby("load_regime", as_index=False).agg(
        observations=(PRICE, "size"), mean_price_usd_mwh=(PRICE, "mean"),
        median_price_usd_mwh=(PRICE, "median"), spike_rate=("price_spike_p95", "mean")
    ).to_csv(PROCESSED_DIR / "load_regime_summary.csv", index=False)
    joint = data.groupby(["load_regime", "renewable_regime"], as_index=False).agg(
        observations=(PRICE, "size"), mean_price_usd_mwh=(PRICE, "mean"),
        median_price_usd_mwh=(PRICE, "median"), spike_rate=("price_spike_p95", "mean")
    )
    joint.to_csv(PROCESSED_DIR / "load_renewable_regime_summary.csv", index=False)
    sensitivity = []
    for threshold in [0.90, 0.95, 0.99]:
        cutoff = data[PRICE].quantile(threshold)
        sensitivity.append(
            {
                "percentile_definition": f"P{int(threshold * 100)}",
                "price_threshold_usd_mwh": cutoff,
                "overall_spike_rate": (data[PRICE] >= cutoff).mean(),
                "extreme_load_low_renewable_spike_rate": (
                    data.loc[
                        data["load_regime"].eq("Extreme load") & data["renewable_regime"].eq("Low renewable"),
                        PRICE,
                    ] >= cutoff
                ).mean(),
            }
        )
    pd.DataFrame(sensitivity).to_csv(PROCESSED_DIR / "spike_threshold_sensitivity.csv", index=False)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    data = query_market()
    annual = annual_summary(data)
    write_tables(data, annual)
    make_figures(data, annual)
    print("Created annual summary tables and six figures.")
    print(annual[["year", "observations", "average_load_mw", "average_solar_mw", "median_price_usd_mwh", "p95_price_usd_mwh"]].to_string(index=False, float_format=lambda value: f"{value:,.1f}"))


if __name__ == "__main__":
    main()
