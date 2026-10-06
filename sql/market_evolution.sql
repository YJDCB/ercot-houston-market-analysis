-- Longitudinal market evolution by calendar year.
SELECT
    year,
    COUNT(*) AS observations,
    ROUND(AVG(system_load_mw), 1) AS average_load_mw,
    ROUND(MAX(system_load_mw), 1) AS peak_load_mw,
    ROUND(AVG(wind_mw), 1) AS average_wind_mw,
    ROUND(AVG(solar_mw), 1) AS average_solar_mw,
    ROUND(AVG(dam_price_usd_mwh), 2) AS mean_price_usd_mwh
FROM market_features
GROUP BY year
ORDER BY year;
