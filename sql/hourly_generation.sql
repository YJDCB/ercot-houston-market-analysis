-- Fuel-mix source data is published as 15-minute interval energy.  The
-- pipeline converts it to MW (MWh × 4) and then takes the hourly mean before
-- loading `generation`.
DROP VIEW IF EXISTS generation_fuel_mix;

CREATE VIEW generation_fuel_mix AS
SELECT
    timestamp,
    natural_gas_mw,
    wind_mw,
    solar_mw,
    coal_mw,
    nuclear_mw,
    biomass_mw,
    hydro_mw,
    other_mw,
    generation_interval_count_per_fuel
FROM generation;
