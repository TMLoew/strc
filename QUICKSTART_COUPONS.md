# Get Coupons Fast - Quick Start Guide

## Current Problem

**97.4% of your 26,453 products are missing coupon data.**

Only 683 products have coupons. You need 25,770 more.

## Fastest Solution (5 Minutes to Start)

### Step 1: Check What's Missing
```bash
poetry run python scripts/check_missing_data.py
```

### Step 2: Start Enrichment
```bash
# Start with 100 products (takes ~5-8 minutes)
poetry run python scripts/enrich_finanzen.py --limit 100
```

That's it! You'll see a progress bar and get ~60-80 products with coupons.

## Scale It Up

### Process 500 Products (~40 minutes)
```bash
poetry run python scripts/enrich_finanzen.py --limit 500
```

### Process All Leonteq Products (~5 hours)
```bash
poetry run python scripts/enrich_finanzen.py --limit 6000
```

### Process Everything (~24 hours in background)
```bash
# Run overnight
nohup poetry run python scripts/enrich_finanzen.py --limit 25770 > enrichment.log 2>&1 &

# Check progress anytime
tail -f enrichment.log
```

## Or Use the Web UI

1. `bash start.sh`
2. Open http://localhost:5173
3. Scroll to "Finanzen.ch Coupon Crawler"
4. Set limit (e.g., 500)
5. Click "🇨🇭 Crawl Finanzen.ch"
6. Watch progress bar

## Filter Options

By default, it targets products missing coupons. You can change:

```bash
# Only missing coupons (default)
--filter missing_coupon

# Only missing barriers
--filter missing_barrier

# Missing either
--filter missing_any

# All products (refresh all data)
--filter all_with_isin
```

## Expected Results

- **Success rate**: 60-80%
- **Speed**: 3-4 seconds per product
- **Final coverage**: 70-80% (from current 2.6%)

## After Enrichment

Check results:
```bash
poetry run python scripts/check_missing_data.py
```

View in UI:
- Go to Products tab
- Products now show coupon rates
- Filter by "Missing Coupons" to see remaining

## If Interrupted

Resume from checkpoint:
```bash
poetry run python scripts/enrich_finanzen.py --resume
```

## Troubleshooting

**"No products need enrichment"**
→ Already done! Check with `check_missing_data.py`

**High failure rate**
→ Normal - some products aren't on finanzen.ch or don't have coupons

**Slow**
→ That's the rate limit (2 seconds between products) - necessary to be respectful

## Next Steps After Coupons

1. **Get barriers** - Run with `--filter missing_barrier`
2. **Enrich Leonteq PDFs** - For remaining Leonteq products
3. **Re-crawl AKB** - Enhanced parser gets more data

---

**Your coupon problem is solved. Just run the command and let it work!** 🚀
