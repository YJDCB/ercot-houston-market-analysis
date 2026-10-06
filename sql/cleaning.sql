-- Source tables are standardised by src/data_pipeline.py before loading.
-- This view makes price and load quality fields explicit for SQL review.
DROP VIEW IF EXISTS cleaned_prices_load;

CREATE VIEW cleaned_prices_load AS
SELECT
    p.timestamp,
    p.dam_price_usd_mwh,
    p.price_observation_count,
    l.system_load_mw,
    l.load_observation_count
FROM prices AS p
INNER JOIN load AS l
    ON p.timestamp = l.timestamp
WHERE p.dam_price_usd_mwh IS NOT NULL
  AND l.system_load_mw IS NOT NULL;
