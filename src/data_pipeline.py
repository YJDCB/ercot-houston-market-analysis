"""Create a reproducible SQLite market database from ERCOT's annual files.

The pipeline keeps the project's three source families separate until SQL joins
them.  It standardises each record to the beginning of its Central-time
delivery hour.  ERCOT's source files use hour-ending labels, so ``01:00``
becomes midnight of the same date.  During daylight-saving changes, source
observations that share a local timestamp are averaged only after their count
is recorded; the spring missing hour is never invented.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
DATABASE = ROOT / "data" / "ercot_market.sqlite"
YEARS = range(2021, 2027)
FUEL_MAP = {
    "Gas": "natural_gas_mw",
    "Gas-CC": "natural_gas_mw",
    "Wind": "wind_mw",
    "Solar": "solar_mw",
    "Coal": "coal_mw",
    "Nuclear": "nuclear_mw",
    "Biomass": "biomass_mw",
    "Hydro": "hydro_mw",
    "Other": "other_mw",
}


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    copy = frame.copy()
    copy.columns = [str(column).strip().lower().replace(" ", "_") for column in copy.columns]
    return copy


def workbook_from_zip(path: Path, member_suffix: str) -> BytesIO:
    with ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(member_suffix.lower()))
        return BytesIO(archive.read(member))


def read_prices() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in YEARS:
        path = RAW_DIR / f"dam_prices_{year}.zip"
        workbook = workbook_from_zip(path, ".xlsx")
        sheets = pd.read_excel(workbook, sheet_name=None)
        for sheet in sheets.values():
            data = normalise_columns(sheet)
            required = {"delivery_date", "hour_ending", "settlement_point", "settlement_point_price"}
            if not required.issubset(data.columns):
                continue
            selected = data.loc[data["settlement_point"].eq("HB_HOUSTON")].copy()
            if selected.empty:
                continue
            hour = selected["hour_ending"].astype(str).str.extract(r"(\d{1,2})", expand=False)
            selected["delivery_hour"] = pd.to_numeric(hour, errors="coerce")
            selected["timestamp"] = pd.to_datetime(selected["delivery_date"], errors="coerce") + pd.to_timedelta(
                selected["delivery_hour"] - 1, unit="h"
            )
            selected["dam_price_usd_mwh"] = pd.to_numeric(selected["settlement_point_price"], errors="coerce")
            selected["source_year"] = year
            selected["repeated_hour_flag"] = selected.get("repeated_hour_flag", "N").fillna("N")
            frames.append(
                selected[
                    [
                        "timestamp",
                        "dam_price_usd_mwh",
                        "source_year",
                        "repeated_hour_flag",
                    ]
                ]
            )
    raw = pd.concat(frames, ignore_index=True).dropna(subset=["timestamp", "dam_price_usd_mwh"])
    return (
        raw.groupby("timestamp", as_index=False)
        .agg(
            dam_price_usd_mwh=("dam_price_usd_mwh", "mean"),
            price_observation_count=("dam_price_usd_mwh", "size"),
            source_year=("source_year", "first"),
        )
        .sort_values("timestamp")
    )


def read_load() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in YEARS:
        path = RAW_DIR / f"native_load_{year}.zip"
        data = normalise_columns(pd.read_excel(workbook_from_zip(path, ".xlsx")))
        if not {"hour_ending", "ercot"}.issubset(data.columns):
            raise ValueError(f"Unexpected ERCOT load format in {path.name}: {data.columns.tolist()}")
        # ERCOT's load files use an hour-ending convention and represent the
        # final interval as `24:00`, which pandas cannot parse directly.  Split
        # the date and hour so that 24:00 correctly maps to 23:00 of the same
        # delivery date rather than becoming a missing value.
        hour = data["hour_ending"].astype(str).str.extract(r"\s(\d{1,2}):", expand=False)
        delivery_hour = pd.to_numeric(hour, errors="coerce")
        delivery_date = data["hour_ending"].astype(str).str.extract(r"^([^\s]+)", expand=False)
        data["timestamp"] = pd.to_datetime(delivery_date, errors="coerce") + pd.to_timedelta(
            delivery_hour - 1, unit="h"
        )
        data["system_load_mw"] = pd.to_numeric(data["ercot"], errors="coerce")
        data["source_year"] = year
        frames.append(data[["timestamp", "system_load_mw", "source_year"]])
    raw = pd.concat(frames, ignore_index=True).dropna(subset=["timestamp", "system_load_mw"])
    return (
        raw.groupby("timestamp", as_index=False)
        .agg(
            system_load_mw=("system_load_mw", "mean"),
            load_observation_count=("system_load_mw", "size"),
            source_year=("source_year", "first"),
        )
        .sort_values("timestamp")
    )


def fuel_workbook(year: int) -> BytesIO | Path:
    if year <= 2024:
        with ZipFile(RAW_DIR / "fuel_mix_2007_2024.zip") as archive:
            member = next(
                name for name in archive.namelist() if name.lower().endswith(f"intgenbyfuel{year}.xlsx")
            )
            return BytesIO(archive.read(member))
    return RAW_DIR / f"fuel_mix_{year}.xlsx"


def quarter_hour_columns(columns: pd.Index) -> list[str]:
    return [str(column) for column in columns if ":" in str(column)]


def read_generation_year(year: int) -> pd.DataFrame:
    book = pd.ExcelFile(fuel_workbook(year))
    frames: list[pd.DataFrame] = []
    for sheet_name in book.sheet_names:
        if sheet_name not in {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}:
            continue
        data = normalise_columns(pd.read_excel(book, sheet_name=sheet_name))
        required = {"date", "fuel", "settlement_type"}
        if not required.issubset(data.columns):
            continue
        data = data.loc[data["settlement_type"].astype(str).str.upper().eq("FINAL")].copy()
        data = data.loc[data["fuel"].isin(FUEL_MAP)].copy()
        quarter_columns = quarter_hour_columns(data.columns)
        if len(quarter_columns) not in {96, 100}:
            raise ValueError(
                f"Expected 96 standard intervals (or 100 during DST fallback) in {year} {sheet_name}, "
                f"found {len(quarter_columns)}"
            )
        values = data[["date", "fuel"] + quarter_columns].melt(
            id_vars=["date", "fuel"], value_vars=quarter_columns, var_name="interval_label", value_name="generation_mw"
        )
        values["quarter_index"] = values.groupby(["date", "fuel"], sort=False).cumcount()
        # November sheets carry the four repeated DST intervals after the normal
        # 96 columns.  Map those intervals back to local hour 01:00; later SQL
        # aggregation retains their observation count rather than discarding it.
        values["hour_offset"] = np.where(
            values["quarter_index"] < 96,
            values["quarter_index"] // 4,
            # The appended labels 01:15 (DST) through 02:00 (DST) are the
            # four quarters of the repeated local 01:00 hour.
            1,
        )
        values["timestamp"] = pd.to_datetime(values["date"], errors="coerce") + pd.to_timedelta(
            values["hour_offset"], unit="h"
        )
        values["fuel_column"] = values["fuel"].map(FUEL_MAP)
        # Fuel Mix interval values are energy over a 15-minute settlement
        # interval.  Multiply MWh by four before taking the hourly mean so the
        # resulting column is comparable to ERCOT's hourly average MW load.
        values["generation_mw"] = pd.to_numeric(values["generation_mw"], errors="coerce") * 4
        frames.append(values[["timestamp", "fuel", "fuel_column", "generation_mw"]])
    long = pd.concat(frames, ignore_index=True).dropna(subset=["timestamp", "generation_mw"])
    # First average the four quarter-hour observations for each original fuel.
    # Only then map fuels: Gas and Gas-CC both map to natural gas and must be
    # *summed*, rather than averaged together.
    hourly_source_fuel = long.groupby(["timestamp", "fuel"], as_index=False).agg(
        generation_mw=("generation_mw", "mean"), interval_count=("generation_mw", "size")
    )
    hourly_by_fuel = (
        hourly_source_fuel.assign(fuel_column=lambda frame: frame["fuel"].map(FUEL_MAP))
        .groupby(["timestamp", "fuel_column"], as_index=False)["generation_mw"]
        .sum()
    )
    hourly = hourly_by_fuel.pivot(
        index="timestamp", columns="fuel_column", values="generation_mw"
    ).reset_index()
    interval_counts = hourly_source_fuel.groupby("timestamp", as_index=False)["interval_count"].max()
    hourly = hourly.merge(interval_counts, on="timestamp", how="left")
    hourly = hourly.rename(columns={"interval_count": "generation_interval_count_per_fuel"})
    hourly["source_year"] = year
    return hourly


def read_generation() -> pd.DataFrame:
    frames = [read_generation_year(year) for year in YEARS]
    data = pd.concat(frames, ignore_index=True)
    for column in sorted(set(FUEL_MAP.values())):
        if column not in data:
            data[column] = 0.0
    value_columns = sorted(set(FUEL_MAP.values()))
    data = data.groupby("timestamp", as_index=False).agg(
        **{column: (column, "mean") for column in value_columns},
        generation_interval_count_per_fuel=("generation_interval_count_per_fuel", "max"),
    )
    return data.sort_values("timestamp")


def write_sql(connection: sqlite3.Connection) -> None:
    for filename in [
        "schema.sql",
        "cleaning.sql",
        "hourly_generation.sql",
        "market_view.sql",
        "market_features.sql",
    ]:
        connection.executescript((SQL_DIR / filename).read_text())


def coverage_table(prices: pd.DataFrame, load: pd.DataFrame, generation: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    tables = {"prices": prices, "load": load, "generation": generation, "market_hourly": market}
    summary = []
    for name, data in tables.items():
        summary.append(
            {
                "table": name,
                "rows": len(data),
                "first_timestamp": data["timestamp"].min(),
                "last_timestamp": data["timestamp"].max(),
                "duplicate_local_timestamps": int(data["timestamp"].duplicated().sum()),
            }
        )
    return pd.DataFrame(summary)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    prices = read_prices()
    load = read_load()
    generation = read_generation()
    with sqlite3.connect(DATABASE) as connection:
        prices.to_sql("prices", connection, if_exists="replace", index=False)
        load.to_sql("load", connection, if_exists="replace", index=False)
        generation.to_sql("generation", connection, if_exists="replace", index=False)
        write_sql(connection)
        market = pd.read_sql_query("SELECT * FROM market_hourly ORDER BY timestamp", connection, parse_dates=["timestamp"])

    prices.to_csv(PROCESSED_DIR / "prices_hourly.csv", index=False)
    load.to_csv(PROCESSED_DIR / "load_hourly.csv", index=False)
    generation.to_csv(PROCESSED_DIR / "generation_hourly.csv", index=False)
    market.to_csv(PROCESSED_DIR / "market_hourly.csv", index=False)
    coverage_table(prices, load, generation, market).to_csv(PROCESSED_DIR / "data_coverage.csv", index=False)
    print(f"Created {DATABASE.name} with {len(market):,} joined market hours.")
    print(coverage_table(prices, load, generation, market).to_string(index=False))


if __name__ == "__main__":
    main()
