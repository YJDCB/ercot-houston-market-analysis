# Data guide

The project keeps raw ERCOT files separate from cleaned tables.  All analysis timestamps represent the start of the ERCOT delivery hour in Central time.

## Sources

- **Prices:** ERCOT Historical DAM Load Zone and Hub Prices, report `NP4-180-ER` / report type `13060`.  The pipeline keeps `HB_HOUSTON`.
- **Load:** ERCOT Hourly Load Data Archives.  The pipeline uses the ERCOT system-total column.
- **Generation:** ERCOT Fuel Mix Reports.  Each source value is energy for a 15-minute interval.  The pipeline converts it to average MW (`MWh × 4`) and then takes an hourly mean before joining it to price and load.

## Processed tables

The pipeline will write the following files after validating source coverage:

| File | Grain | Purpose |
|---|---|---|
| `prices_hourly.csv` | hour × settlement point | cleaned DAM price input |
| `load_hourly.csv` | hour | ERCOT system load input |
| `generation_hourly.csv` | hour | hourly fuel mix input |
| `market_hourly.csv` | hour | joined analysis table for `HB_HOUSTON` |

Raw and processed data are not committed to Git.  All scripts are designed to be reproducible from the official downloads.

## Coverage and time treatment

The three source families have different latest dates.  The joined analysis table therefore ends on **2026-06-30**, the final date common to all downloaded source files.  It contains 48,161 local delivery hours from 2021-01-01 onward.

ERCOT labels price and load with **hour ending**.  The pipeline maps `01:00` to the hour beginning at midnight and maps `24:00` to the hour beginning at 23:00 without losing the final daily observation.  Fuel Mix reports add four explicitly labeled intervals during the November daylight-saving fallback.  Those source observations are mapped back to the repeated local hour and averaged, while `generation_interval_count_per_fuel` preserves the source count (normally four; eight for a repeated local hour).  The missing spring local hour is not created.
