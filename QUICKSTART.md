# Quick Start Guide - Get Complete Product Data

## Problem: Missing Product Details

Your database currently has products with **missing details**:
- **Swissquote**: 1,046 products - only ISIN, no issuer/currency/underlyings
- **Leonteq HTML**: 127 products - only ISIN/currency, missing issuer/type/underlyings
- **AKB**: 1,767 products - has issuer/type but missing underlyings

## Solution: Leonteq API (Best Data Source)

The Leonteq API provides **complete data** for all products:
- ✓ All identifiers (ISIN, Valor, WKN, Symbol, LEI)
- ✓ Issuer name and details
- ✓ Product type & SSPA category
- ✓ Currency & denomination
- ✓ **Complete underlying details** (names, ISINs, weights, RIC codes, Bloomberg tickers)
- ✓ **Strike & barrier levels**
- ✓ All dates (maturity, issue, fixing, subscription)
- ✓ Listing venues
- ✓ Coupon information
- ✓ Settlement details
- ✓ Participation rates

## Steps to Get Complete Data

### Step 1: Extract API Token (Automated)

Run the automated token extraction script:

```bash
cd "/Applications/Structured Products Analysis"
poetry run python3 scripts/get_leonteq_token.py
```

**What happens:**
1. Browser opens to Leonteq website
2. You browse the site normally (click on products, etc.)
3. Script automatically captures JWT token from network requests
4. Token is saved to `.env` file
5. Token is verified with test API call

**Duration:** ~30 seconds

---

### Step 2: Run the Crawler

Once the token is saved, trigger the crawler:

**Option A: Via Frontend**
1. Open http://localhost:5173
2. Look for "Leonteq API" crawler section (if added to UI)
3. Click "Run Leonteq API Crawler"

**Option B: Via API**
```bash
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api
```

**Option C: Via Python**
```bash
poetry run python3 -c "
from backend.app.services.leonteq_api_crawler_service import crawl_leonteq_api
result = crawl_leonteq_api()
print(f'Imported {len(result[\"ids\"])} products')
"
```

---

### Step 3: Monitor Progress

Watch the crawler in real-time:

**Status Dashboard:**
```
http://localhost:8000/static/status.html
```

**CLI Monitor:**
```bash
poetry run python3 scripts/monitor_crawl.py --latest
```

**Expected progress:**
- Total products: ~1,200+
- Processing rate: ~5-10 products/second
- Total time: ~3-5 minutes
- Errors: Should be minimal (if any)

---

### Step 4: View Results

Once complete, view the imported products:

```bash
# View latest Leonteq API products
poetry run python3 scripts/view_products.py --source leonteq_api --limit 5

# Search by ISIN
poetry run python3 scripts/view_products.py --isin CH1234567890

# View statistics
poetry run python3 scripts/view_products.py --stats
```

---

## What You'll Get

After the crawler completes, you'll have:

✓ **~1,200+ Leonteq products** with complete details
✓ **Full underlying information** for basket products
✓ **Accurate strike/barrier levels**
✓ **All financial metrics** (coupon rates, yields, etc.)
✓ **High confidence scores** (0.9) from API vs 0.6 from HTML parsing

---

## Troubleshooting

### Token Extraction Fails

**Problem:** Browser opens but no token is captured

**Solution:** Make sure to actually browse the site:
- Click on "Products" tab
- Browse a few products
- The API calls will be triggered automatically

**Alternative:** Use manual method:
1. Open DevTools (F12) → Network tab
2. Browse Leonteq site
3. Find `/rfb-api/products` request
4. Copy `Authorization: Bearer <token>` header
5. Add to `.env`: `SPA_LEONTEQ_API_TOKEN=<token>`

### Crawler Fails with "Token Invalid"

**Problem:** API returns 401 Unauthorized

**Solution:** Token may have expired, re-run extraction:
```bash
poetry run python3 scripts/get_leonteq_token.py
```

### Crawler Timeout

**Problem:** Rate limiting or network issues

**Solution:** Adjust rate limit in `.env`:
```bash
SPA_LEONTEQ_API_RATE_LIMIT_MS=500  # Increase delay between requests
```

---

## Next Steps

After importing Leonteq API data:

1. **Compare data sources** - See which source provides best data for each field
2. **Merge logic** - Optionally create merged records combining API + HTML data
3. **Fix other parsers** - Enhance Swissquote/Leonteq HTML parsers as fallback
4. **Add to daily crawl** - Include in automated rotation

---

## Technical Details

**Deduplication:**
- Hash: `sha256("leonteq_api:{isin}")`
- Multiple sources for same ISIN will coexist
- No automatic merging (intentional - allows comparison)

**Database:**
- Table: `products`
- Source: `leonteq_api`
- Normalized fields: `normalized_json` column
- Raw API response: `raw_text` column

**Performance:**
- Parallel processing: 4 workers (configurable)
- Rate limiting: 100ms between requests (configurable)
- Memory efficient: Streams paginated results
- Progress tracked in `crawl_runs` table

---

## Files Created

- `scripts/get_leonteq_token.py` - Automated token extraction
- `scripts/test_leonteq_api.py` - Test API connection
- `core/sources/leonteq_api.py` - API fetcher & parser (improved)
- `backend/app/services/leonteq_api_crawler_service.py` - Crawler service
- `backend/app/static/status.html` - Status dashboard
- `PARSER_ISSUES.md` - Analysis of missing data issues
- `QUICKSTART.md` - This guide

---

## Summary

🎯 **Goal:** Get complete product details (underlyings, currency, strikes, barriers)

✅ **Solution:** Use Leonteq API (most comprehensive data source)

⚡ **Time:** ~5 minutes to set up and run

📊 **Result:** ~1,200+ products with full details imported to database
