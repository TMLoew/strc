CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    isin TEXT,
    valor_number TEXT,
    issuer_name TEXT,
    product_type TEXT,
    currency TEXT,
    maturity_date TEXT,
    review_status TEXT NOT NULL DEFAULT 'not_reviewed',
    source_kind TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    raw_text TEXT,
    source_file_path TEXT,
    source_file_hash_sha256 TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_isin ON products(isin);
CREATE INDEX IF NOT EXISTS idx_products_valor ON products(valor_number);
CREATE INDEX IF NOT EXISTS idx_products_issuer ON products(issuer_name);
CREATE INDEX IF NOT EXISTS idx_products_type ON products(product_type);
CREATE INDEX IF NOT EXISTS idx_products_currency ON products(currency);
CREATE INDEX IF NOT EXISTS idx_products_maturity ON products(maturity_date);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    checkpoint_offset INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_status ON crawl_runs(status);
