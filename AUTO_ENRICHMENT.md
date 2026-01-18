# Auto-Enrichment Feature

## Overview

The auto-enrichment feature continuously enriches products in the background, progressively filling in missing coupon and barrier data. It remembers its position and automatically resumes where it left off, making it perfect for long-running data collection.

## Key Features

- **Continuous Background Processing**: Runs autonomously without user intervention
- **Position Memory**: Remembers exactly where it stopped and resumes seamlessly
- **Progress Tracking**: Real-time stats on enriched products, failures, and remaining work
- **Configurable Batch Size**: Control how many products to process per cycle
- **Safe Interruption**: Can be stopped and resumed at any time without data loss
- **Web UI Controls**: Simple start/stop/reset interface

## How It Works

### The Cycle

1. **Fetch Batch**: Gets next N products with missing coupons (based on offset)
2. **Enrich**: Scrapes data from finanzen.ch for each product
3. **Save**: Updates database with enriched data
4. **Update Position**: Increments offset and saves to disk
5. **Wait**: Delays 30 seconds before next cycle
6. **Repeat**: Continues until stopped or no products remain

### State Persistence

Position is saved to `data/auto_enrich_state.json`:

```json
{
  "finanzen_offset": 150,
  "leonteq_offset": 0,
  "total_enriched": 89,
  "total_failed": 61,
  "last_run": 1706789456.23
}
```

This file is:
- Updated after each cycle
- Loaded on startup/resume
- Preserved across backend restarts
- Reset only when explicitly requested

## Usage

### Via Web UI (Recommended)

1. **Start Application**: `bash start.sh` or open the `.app`
2. **Navigate**: Go to Settings tab → Auto-Enrichment section
3. **Configure**: Set batch size (default: 10 products per cycle)
4. **Start**: Click "▶️ Start Auto-Enrichment"
5. **Monitor**: Watch real-time stats update every 5 seconds
6. **Stop** (optional): Click "⏹️ Stop Auto-Enrichment" when desired

**Reset Position**: Click "🔄 Reset Position" to start from beginning (only when stopped)

### Via API

```bash
# Start auto-enrichment (10 products per cycle)
curl -X POST "http://localhost:8000/api/enrich/auto/start?batch_size=10"

# Returns:
# {
#   "status": "started",
#   "batch_size": 10,
#   "current_offset": 150,
#   "total_enriched": 89,
#   "total_failed": 61
# }

# Check status
curl "http://localhost:8000/api/enrich/auto/status"

# Returns:
# {
#   "running": true,
#   "finanzen_offset": 150,
#   "total_enriched": 89,
#   "total_failed": 61,
#   "total_missing": 33000,
#   "progress_pct": 12,
#   "last_run": 1706789456.23
# }

# Stop auto-enrichment
curl -X POST "http://localhost:8000/api/enrich/auto/stop"

# Reset position to start from beginning
curl -X POST "http://localhost:8000/api/enrich/auto/reset"
```

## Configuration

### Batch Size

**Small (5-10 products)**: Conservative, slower but gentle on server
- Processing time: ~2-3 minutes per cycle
- Good for: Background enrichment during work hours

**Medium (10-20 products)**: Balanced (recommended)
- Processing time: ~4-6 minutes per cycle
- Good for: General purpose, overnight enrichment

**Large (20-50 products)**: Aggressive, faster but more intensive
- Processing time: ~10-20 minutes per cycle
- Good for: One-time bulk enrichment, when finanzen.ch allows

## Performance

### Expected Throughput

| Batch Size | Cycle Time | Products/Hour | Products/Day |
|------------|------------|---------------|--------------|
| 5          | 2 min      | ~100          | ~2,400       |
| 10         | 4 min      | ~120          | ~2,900       |
| 20         | 8 min      | ~130          | ~3,100       |
| 50         | 20 min     | ~140          | ~3,400       |

*Actual throughput depends on network speed and finanzen.ch response times*

### Success Rate

- **60-80%** enrichment success rate (products found and parsed)
- **20-40%** failure rate (not found, no data, parsing errors)

**Why failures occur**:
- Product not listed on finanzen.ch (~10-15%)
- Product type doesn't have coupons (~10-15%)
- Network timeouts (~1-2%)
- Parsing errors (~5-10%)

## Best Practices

### When to Use Auto-Enrichment

✅ **Good Use Cases**:
- Initial database population (thousands of products)
- Overnight/weekend enrichment (leave running)
- Background data improvement during development
- Filling gaps after new product imports

❌ **When to Use Manual Enrichment Instead**:
- Need specific products enriched immediately
- Testing/debugging enrichment logic
- Only a few products need updating (<100)
- Want to control exact order of processing

### Operational Tips

1. **Start Small**: Begin with batch_size=10 to verify it works
2. **Monitor First Cycle**: Watch the first few products to ensure success
3. **Leave Running**: Safe to leave running overnight or over weekends
4. **Check Logs**: Backend logs show detailed progress and errors
5. **Resume Anytime**: Backend restart won't lose progress

## Monitoring

### Web UI Stats

The Settings tab shows real-time stats:

- **Status**: 🟢 Running or ⚪ Stopped
- **Progress**: Percentage complete (estimated)
- **Enriched**: Total products successfully enriched
- **Failed**: Total products that couldn't be enriched
- **Position**: Current offset in product list
- **Remaining**: Approximate products still missing data

Stats update every 5 seconds via polling.

### Backend Logs

Check backend terminal for detailed logging:

```
INFO: Starting auto-enrich cycle (batch_size=10)
INFO: [1/10] Processing Barrier Reverse Convertible (CH1234567890)
INFO: Product 42 (CH1234567890): Enriched successfully
INFO: [2/10] Processing Express Certificate (CH0987654321)
WARNING: Product 43 (CH0987654321): No HTML fetched
INFO: Auto-enrich cycle complete: {'finanzen_enriched': 7, 'finanzen_failed': 3, 'total_processed': 10}
DEBUG: Saved auto-enrich state: {'finanzen_offset': 160, 'total_enriched': 96, ...}
```

## Troubleshooting

### "Auto-enrichment is already running"

**Cause**: Another instance is running (or crashed without cleanup)

**Solution**:
1. Check if it's actually running: refresh UI and check status
2. If stuck, restart backend: `lsof -ti:8000 | xargs kill -9 && bash start.sh`

### High Failure Rate (>50%)

**Causes**:
- Many products are trackers/warrants (don't have coupons)
- ISINs are old or invalid
- Network issues
- Site structure changed

**Solutions**:
- Normal for certain product types - check logs for specific errors
- Reduce batch size if network is unstable
- Check a few failed ISINs manually on finanzen.ch

### Progress Seems Stuck

**Check**:
1. Backend logs - is it actually processing?
2. UI status - is it updating every 5 seconds?
3. State file - is offset incrementing?

**Solutions**:
- If logs show progress, UI polling may have stopped (refresh page)
- If truly stuck, stop and restart auto-enrichment

### "Cannot reset while auto-enrichment is running"

**Cause**: Tried to reset while still running

**Solution**: Stop auto-enrichment first, then reset

## File Locations

- **State File**: `data/auto_enrich_state.json`
- **Backend Service**: `backend/app/services/auto_enrichment.py`
- **API Routes**: `backend/app/api/routes_enrich.py` (lines 25-100)
- **Frontend Controls**: `frontend/src/App.jsx` (Settings tab)

## API Reference

### POST /api/enrich/auto/start

Start continuous auto-enrichment.

**Query Parameters**:
- `batch_size` (int, default: 10): Products per cycle

**Response**:
```json
{
  "status": "started",
  "batch_size": 10,
  "current_offset": 150,
  "total_enriched": 89,
  "total_failed": 61
}
```

### POST /api/enrich/auto/stop

Stop auto-enrichment gracefully.

**Response**:
```json
{
  "status": "stopped",
  "total_enriched": 89,
  "total_failed": 61
}
```

### GET /api/enrich/auto/status

Get current auto-enrichment status.

**Response**:
```json
{
  "running": true,
  "finanzen_offset": 150,
  "total_enriched": 89,
  "total_failed": 61,
  "total_missing": 33000,
  "progress_pct": 12,
  "last_run": 1706789456.23
}
```

### POST /api/enrich/auto/reset

Reset position to start from beginning.

**Note**: Cannot reset while running. Stop first.

**Response**:
```json
{
  "status": "reset",
  "message": "Auto-enrichment will start from the beginning on next run"
}
```

## Example Workflow

### First-Time Setup (30,000 products missing coupons)

1. **Start**: `bash start.sh`
2. **Navigate**: Settings tab → Auto-Enrichment
3. **Configure**: Set batch_size = 20
4. **Start**: Click "▶️ Start"
5. **Leave Running**: Close laptop, leave overnight
6. **Check Next Day**:
   - ~3,000 products enriched
   - ~27,000 remaining
7. **Continue**: Leave running for ~10 days
8. **Final Result**: ~21,000 enriched (70%), ~9,000 failed (30%)

### Quick Top-Up (after importing 500 new products)

1. **Settings Tab**: Check auto-enrich status
2. **If Stopped**: Click "▶️ Start" (it will continue from offset)
3. **If Running**: Already being processed automatically
4. **Result**: New products enriched within 1-2 hours

## Summary

**Auto-enrichment is the easiest way to progressively improve data quality**:

✅ Set it and forget it
✅ Remembers position automatically
✅ Safe to interrupt and resume
✅ Real-time progress tracking
✅ Perfect for large-scale enrichment

**Just start it and let it run in the background while you do other work!**
