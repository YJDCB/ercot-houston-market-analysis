DROP VIEW IF EXISTS market_hourly;

CREATE VIEW market_hourly AS
WITH joined AS (
    SELECT
        c.timestamp,
        c.dam_price_usd_mwh,
        c.system_load_mw,
        g.natural_gas_mw,
        g.wind_mw,
        g.solar_mw,
        g.coal_mw,
        g.nuclear_mw,
        g.biomass_mw,
        g.hydro_mw,
        g.other_mw
    FROM cleaned_prices_load AS c
    INNER JOIN generation_fuel_mix AS g
        ON c.timestamp = g.timestamp
), features AS (
    SELECT
        *,
        CAST(strftime('%Y', timestamp) AS INTEGER) AS year,
        CAST(strftime('%m', timestamp) AS INTEGER) AS month,
        CAST(strftime('%H', timestamp) AS INTEGER) AS hour_of_day,
        CAST(strftime('%w', timestamp) AS INTEGER) AS day_of_week,
        CASE
            WHEN CAST(strftime('%m', timestamp) AS INTEGER) IN (12, 1, 2) THEN 'Winter'
            WHEN CAST(strftime('%m', timestamp) AS INTEGER) IN (3, 4, 5) THEN 'Spring'
            WHEN CAST(strftime('%m', timestamp) AS INTEGER) IN (6, 7, 8) THEN 'Summer'
            ELSE 'Fall'
        END AS season,
        wind_mw + solar_mw AS renewable_mw,
        LAG(dam_price_usd_mwh, 24) OVER (ORDER BY timestamp) AS prior_day_same_hour_price,
        AVG(system_load_mw) OVER (
            ORDER BY timestamp ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS rolling_24h_load_mw
    FROM joined
)
SELECT * FROM features;
