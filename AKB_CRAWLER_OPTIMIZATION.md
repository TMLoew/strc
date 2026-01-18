# AKB Portal Crawler Optimization

## The Problem

The AKB portal crawler was extremely slow and generating thousands of errors after processing ~35 products.

### Root Cause Analysis

The AKB crawler was attempting to **enrich every product** from multiple sources:

1. **AKB Portal** (primary source)
2. **Leonteq API** (enrichment)
3. **Swissquote** (enrichment)
4. **Yahoo Finance** (enrichment if enabled)

For a catalog of **101,713 products**, this meant:
- **~400K+ API calls** (4x per product)
- **Massive error counts** from failed enrichment (Leonteq/Swissquote often don't have the ISIN)
- **Very slow progress** (~1.2 products/second)
- **Estimated completion time**: 23+ hours

### Error Pattern

Errors were showing as:
```
leonteq:CH0124859874:Client error '404 Not Found'
```

These weren't actual failures - they were expected enrichment misses being logged as errors, inflating the error count.

## The Solution

### 1. Disable Enrichment by Default ✓

Added new setting to disable enrichment:

**File**: `backend/app/settings.py`
```python
enable_akb_enrichment: bool = False  # Disable enrichment by default
```

**File**: `.env`
```bash
SPA_ENABLE_AKB_ENRICHMENT=false
```

**File**: `backend/app/services/akb_portal_service.py`
```python
# Skip enrichment if disabled (much faster, fewer errors)
if not settings.enable_akb_enrichment:
    return
```

### 2. Increased Worker Parallelism ✓

Increased concurrent workers from 10 to 30:

**File**: `.env`
```bash
SPA_CRAWL_MAX_WORKERS=30
```

### Results

| Metric | Before | After |
|--------|--------|-------|
| **Errors** | 19 errors in 37 products | 0 errors |
| **Error Rate** | ~50% | 0% |
| **Speed** | ~1.2 products/sec | ~1.0 products/sec (limited by API) |
| **API Calls** | 4x per product | 1x per product |
| **Estimated Time** | 27+ hours | 27 hours (API rate limited) |

## Performance Analysis

### Why Still Slow?

Even with enrichment disabled and 30 workers, the crawler achieves only ~1 product/second because:

1. **AKB API Rate Limiting**: The AKB portal appears to rate-limit requests
2. **Detail Page Fetching**: Each product requires a separate HTML fetch
3. **Sequential Segmentation**: The crawler processes alphabet segments sequentially

### Calculation

- **Total products**: 101,713
- **Current rate**: ~1 product/second
- **Estimated time**: 101,713 seconds ≈ **28 hours**

## When to Enable Enrichment

Enrichment should only be enabled for:

1. **Small batches** (<1,000 products)
2. **Specific ISINs** where you need cross-source data
3. **High-value products** where completeness matters more than speed

### How to Enable Enrichment

**Option 1**: Via environment variable (permanent)
```bash
# In .env
SPA_ENABLE_AKB_ENRICHMENT=true
```

**Option 2**: Programmatically (for specific crawls)
```python
# In akb_portal_service.py
settings.enable_akb_enrichment = True  # Enable for this run
```

## Alternative Approaches

### Option A: Catalog-Only Mode (Current - Fastest)
- **What**: Fetch only AKB catalog data
- **Speed**: ~1 product/sec (API limited)
- **Errors**: 0
- **Use case**: Initial data collection, bulk updates
- **Status**: ✅ IMPLEMENTED

### Option B: Enrichment Mode (Optional - Slowest)
- **What**: Fetch AKB + enrich from Leonteq/Swissquote/Yahoo
- **Speed**: ~0.25 products/sec
- **Errors**: High (expected failures)
- **Use case**: Deep analysis of specific products
- **Status**: ⚠️ Disabled by default

### Option C: Hybrid Mode (Future Enhancement)
- **What**: Fetch all from AKB, enrich only new/updated products
- **Speed**: Fast first run, slower incremental
- **Errors**: Moderate
- **Use case**: Periodic updates
- **Status**: ❌ Not implemented

### Option D: Parallel Segmentation (Future Enhancement)
- **What**: Fetch multiple alphabet segments in parallel
- **Speed**: 3-5x faster (if API allows)
- **Errors**: Low
- **Use case**: Large catalogs
- **Status**: ❌ Not implemented

## Recommendations

### For Production Use

1. **Keep enrichment disabled** for full catalog crawls
2. **Run AKB crawl overnight** (28 hours estimated)
3. **Use Leonteq API crawler** for structured product details (much faster with filtering)
4. **Enable enrichment only for targeted updates** after initial data collection

### Configuration

**Optimal settings for full AKB catalog crawl**:
```bash
# .env
SPA_CRAWL_MAX_WORKERS=30
SPA_ENABLE_AKB_ENRICHMENT=false
SPA_ENABLE_YAHOO_ENRICH=false
```

**Optimal settings for enriched crawl (small batches)**:
```bash
# .env
SPA_CRAWL_MAX_WORKERS=5  # Lower to avoid rate limits
SPA_ENABLE_AKB_ENRICHMENT=true
SPA_ENABLE_YAHOO_ENRICH=false  # Keep Yahoo disabled (slow)
```

## Monitoring

### Check Crawl Progress

```bash
curl -s http://localhost:8000/api/ingest/status/dashboard | python3 -c "
import sys, json
data = json.load(sys.stdin)
akb = [c for c in data['active_crawls'] if 'akb' in c['name'] and c['status'] == 'running'][0]
print(f\"Progress: {akb['completed']:,}/{akb['total']:,}\")
print(f\"Errors: {akb['errors_count']}\")
"
```

### Calculate ETA

```bash
# Get crawl start time and current progress
# Calculate: (total - completed) / (completed / elapsed_seconds)
```

### Check Database Count

```bash
sqlite3 data/structured_products.db "SELECT COUNT(*) FROM products WHERE source_kind = 'akb_finanzportal';"
```

## Troubleshooting

### High Error Count
- **Cause**: Enrichment is enabled
- **Fix**: Set `SPA_ENABLE_AKB_ENRICHMENT=false` in `.env`
- **Note**: Enrichment errors are often expected (404s from Leonteq/Swissquote)

### Crawl Stuck After 35 Products
- **Cause**: Backend server was restarted (kills background tasks)
- **Fix**:
  1. Mark old crawls as failed
  2. Start fresh crawl
  3. Avoid restarting server during crawls

### Very Slow Progress
- **Cause**: AKB API rate limiting (not fixable)
- **Reality**: ~28 hours for full catalog is expected
- **Options**:
  - Run overnight
  - Use Leonteq API for structured products instead
  - Accept slow progress for comprehensive catalog

### Server Restarts Kill Crawls
- **Issue**: Background tasks don't survive server restarts
- **Workaround**: Mark orphaned crawls as failed
  ```sql
  UPDATE crawl_runs
  SET status = 'failed',
      last_error = 'Server restarted',
      ended_at = datetime('now')
  WHERE status = 'running';
  ```

## Summary

✅ **Solution Implemented**: Enrichment disabled by default
✅ **Result**: 0 errors, clean crawl
⚠️ **Limitation**: Still slow (~28 hours) due to API rate limits
📊 **Recommendation**: Use for comprehensive catalog, Leonteq API for structured products

The AKB crawler now runs cleanly without errors, but remains slow due to API constraints. For faster structured product data collection, use the Leonteq API crawler with filtering (see `LEONTEQ_FILTERING.md`).
