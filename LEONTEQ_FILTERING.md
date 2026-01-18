# Leonteq API Filtering Guide

The Leonteq API crawler now supports filtering to fetch specific subsets of products instead of the entire catalog.

## Features

### 1. Recursive Segmentation (Automatic)
The crawler automatically bypasses the 10,000 product API limit using recursive alphabet-based segmentation:
- If total products < 10K → fetches directly
- If total products ≥ 10K → segments by underlying name (A-Z, 0-9)
- If any segment ≥ 10K → recursively subdivides (AA, AB, AC, etc.)
- **Scales indefinitely** - can handle millions of products

### 2. Product Type Filtering
Filter by specific product types (e.g., warrants, barrier reverse convertibles, autocallables).

**Example:**
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -H "Content-Type: application/json" \
  -d '{"product_types": ["PT_BARRIER_REVERSE_CONVERTIBLE", "PT_AUTOCALLABLE"]}'
```

**Common Product Types:**
- `PT_WARRANT` - Warrants
- `PT_BARRIER_REVERSE_CONVERTIBLE` - Barrier Reverse Convertibles
- `PT_AUTOCALLABLE` - Autocallables
- `PT_BONUS_CERTIFICATE` - Bonus Certificates
- `PT_TRACKER_CERTIFICATE` - Tracker Certificates
- `PT_DISCOUNT_CERTIFICATE` - Discount Certificates
- `PT_OUTPERFORMANCE_CERTIFICATE` - Outperformance Certificates

### 3. Symbol Filtering
Filter by underlying symbols (e.g., AAPL, GOOGL, SMI).

**Example:**
```bash
# Fetch only products on Apple
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL"]}'

# Fetch products on multiple underlyings
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "GOOGL", "MSFT", "SMI"]}'
```

### 4. Currency Filtering
Filter by currency (e.g., CHF, USD, EUR).

**Example:**
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -H "Content-Type: application/json" \
  -d '{"currencies": ["CHF"]}'
```

### 5. Combined Filtering
You can combine multiple filters:

**Example:**
```bash
# Fetch CHF-denominated warrants on Apple
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -H "Content-Type: application/json" \
  -d '{
    "product_types": ["PT_WARRANT"],
    "symbols": ["AAPL"],
    "currencies": ["CHF"]
  }'
```

## API Endpoints

### Start Filtered Crawl
**POST** `/api/ingest/crawl/leonteq-api`

**Request Body:**
```json
{
  "product_types": ["PT_WARRANT"],    // Optional: filter by product type
  "symbols": ["AAPL", "GOOGL"],       // Optional: filter by symbols
  "currencies": ["CHF", "USD"]        // Optional: filter by currency
}
```

**Response:**
```json
{
  "run_id": "uuid-string"
}
```

### Check Crawl Status
**GET** `/api/ingest/crawl/status/{run_id}`

**Response:**
```json
{
  "id": "uuid-string",
  "name": "leonteq_api",
  "status": "running",
  "total": 14059,
  "completed": 5838,
  "errors_count": 0,
  "last_error": null,
  "started_at": "2026-01-18T13:15:39.467002+00:00",
  "updated_at": "2026-01-18T13:24:15.123456+00:00",
  "ended_at": null,
  "checkpoint_offset": 0
}
```

### Get Available Product Types
**GET** `/api/ingest/leonteq-api/product-types`

Returns list of product types found in your database with counts.

**Response:**
```json
{
  "product_types": [
    {
      "code": "PT_WARRANT",
      "name": "Warrant",
      "count": 8234
    },
    {
      "code": "PT_BARRIER_REVERSE_CONVERTIBLE",
      "name": "Barrier Reverse Convertible",
      "count": 2156
    }
  ]
}
```

## Technical Details

### Rate Limiting
- Default: 500ms between API requests (configurable via `SPA_LEONTEQ_API_RATE_LIMIT_MS`)
- Slower rate limits = more reliable, less chance of API throttling

### Retry Logic
- Automatically retries on 500 errors or connection drops
- 3 attempts with 5-second delays
- Helps handle temporary API issues

### Deduplication
- Products are deduplicated based on `source_file_hash_sha256` (derived from ISIN + source)
- Re-running a crawl won't create duplicates

### How Symbol Filtering Works
When you filter by symbols, the crawler:
1. Uses the `omni` search parameter in the Leonteq API
2. Still applies recursive segmentation if needed
3. Combines symbol filter with alphabet segmentation for large result sets

Example: `{"symbols": ["AAPL"]}` translates to API filter `{"omni": "AAPL"}`

## Use Cases

### 1. Incremental Updates
Fetch only new product types added since last crawl:
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -d '{"product_types": ["PT_EXPRESS_CERTIFICATE"]}'
```

### 2. Focused Analysis
Analyze products on specific underlyings:
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -d '{"symbols": ["SMI", "SPX", "SX5E"]}'  # Swiss, US, European indices
```

### 3. Market Segment Research
Study specific product categories:
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -d '{"product_types": ["PT_BARRIER_REVERSE_CONVERTIBLE", "PT_AUTOCALLABLE"]}'
```

### 4. Currency-Specific Analysis
Analyze CHF market only:
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api \
  -d '{"currencies": ["CHF"]}'
```

## Performance Notes

- **Full catalog** (14K+ products): ~2-3 hours with 500ms rate limit
- **Single symbol** (e.g., AAPL): ~5-10 minutes
- **Single product type**: Varies (warrants: ~1-2 hours, less common types: faster)
- **Combined filters**: Faster (fewer products to fetch)

## Troubleshooting

### Crawl fails with 500 error
- Increase rate limit: `SPA_LEONTEQ_API_RATE_LIMIT_MS=1000` (slower but safer)
- Check if segment exceeds 10K (logged during crawl)
- Retry logic will attempt 3 times automatically

### No products returned
- Check if filter values are correct
- Verify token is valid: `SPA_LEONTEQ_API_TOKEN` in `.env`
- Check crawl status for errors

### Slow performance
- Decrease rate limit (but increases risk of throttling)
- Use more specific filters to reduce total products
- Run during off-peak hours

## Future Enhancements

Potential improvements:
- **Date range filtering**: Fetch only products with specific maturity dates
- **Strike level filtering**: Filter by strike price ranges
- **Checkpoint support for filtered crawls**: Resume interrupted filtered crawls
- **Parallel segment fetching**: Fetch multiple segments simultaneously
