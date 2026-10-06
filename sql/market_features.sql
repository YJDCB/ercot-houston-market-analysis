-- Market regimes are relative to each calendar year.  This avoids treating a
-- normal 2026 load level as an extreme 2021 condition simply because ERCOT
-- demand and renewable capacity changed over time.
DROP VIEW IF EXISTS market_features;

CREATE VIEW market_features AS
WITH ranked AS (
    SELECT
        *,
        NTILE(10) OVER (PARTITION BY year ORDER BY system_load_mw) AS load_decile,
        NTILE(3) OVER (PARTITION BY year ORDER BY renewable_mw) AS renewable_tercile,
        CUME_DIST() OVER (ORDER BY dam_price_usd_mwh) AS overall_price_cume_dist,
        LAG(dam_price_usd_mwh, 1) OVER (ORDER BY timestamp) AS prior_hour_price
    FROM market_hourly
)
SELECT
    *,
    CASE
        WHEN load_decile <= 3 THEN 'Low load'
        WHEN load_decile <= 7 THEN 'Medium load'
        WHEN load_decile <= 9 THEN 'High load'
        ELSE 'Extreme load'
    END AS load_regime,
    CASE
        WHEN renewable_tercile = 1 THEN 'Low renewable'
        WHEN renewable_tercile = 2 THEN 'Medium renewable'
        ELSE 'High renewable'
    END AS renewable_regime,
    CASE WHEN overall_price_cume_dist >= 0.95 THEN 1 ELSE 0 END AS price_spike_p95
FROM ranked;
