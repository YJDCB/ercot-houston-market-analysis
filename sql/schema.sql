DROP VIEW IF EXISTS market_hourly;

CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_load_timestamp ON load(timestamp);
CREATE INDEX IF NOT EXISTS idx_generation_timestamp ON generation(timestamp);
