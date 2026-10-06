-- Price-spike rate by supply-demand regime.  `price_spike_p95` is defined
-- using the full sample's empirical price distribution in market_features.
SELECT
    load_regime,
    renewable_regime,
    COUNT(*) AS observations,
    ROUND(AVG(dam_price_usd_mwh), 2) AS mean_price_usd_mwh,
    ROUND(100.0 * AVG(price_spike_p95), 2) AS p95_spike_rate_pct
FROM market_features
GROUP BY load_regime, renewable_regime
ORDER BY
    CASE load_regime
        WHEN 'Low load' THEN 1 WHEN 'Medium load' THEN 2
        WHEN 'High load' THEN 3 ELSE 4 END,
    CASE renewable_regime
        WHEN 'Low renewable' THEN 1 WHEN 'Medium renewable' THEN 2 ELSE 3 END;
