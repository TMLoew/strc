# Enrichment State Persistence

## Overview

Both Leonteq PDF enrichment and Finanzen.ch auto-enrichment now save their progress automatically, allowing you to resume exactly where you left off between runs.

## Features Implemented

### 1. Leonteq PDF Enrichment State Persistence

**State File**: `data/leonteq_enrich_state.json`

**What's Saved**:
- `offset`: Current position in product list
- `total_enriched`: Total products successfully enriched (cumulative)
- `total_failed`: Total products that failed enrichment (cumulative)
- `last_run`: Timestamp of last enrichment

**How It Works**:
1. **Start enrichment** - Loads saved state, resumes from last offset
2. **Every 5 products** - Saves progress to disk
3. **On completion** - Saves final state
4. **Next run** - Automatically continues from where it stopped

**API Endpoints**:

```bash
# Check Leonteq enrichment status
GET /api/enrich/leonteq/status

# Response:
{
  "offset": 150,
  "total_enriched": 89,
  "total_failed": 61,
  "last_run": 1706789456.23
}

# Reset Leonteq position (start from beginning)
POST /api/enrich/leonteq/reset

# Response:
{
  "status": "reset",
  "message": "Leonteq enrichment will start from the beginning on next run"
}
```

**Example Workflow**:

```
Run 1: Process 100 products
  - Enriches products 0-99
  - Saves: offset=100, enriched=67, failed=33

Run 2: Process 100 more products
  - Automatically starts at offset 100
  - Enriches products 100-199
  - Saves: offset=200, enriched=134, failed=66

Run 3: Process 50 more products
  - Starts at offset 200
  - Enriches products 200-249
  - Saves: offset=250, enriched=168, failed=82
```

### 2. Auto-Enrichment (Finanzen.ch)

**State File**: `data/auto_enrich_state.json`

**What's Saved**:
- `finanzen_offset`: Current position in Finanzen.ch enrichment
- `leonteq_offset`: Reserved for future Leonteq auto-enrichment
- `total_enriched`: Total products successfully enriched
- `total_failed`: Total products that failed
- `last_run`: Timestamp

**How It Works**:
1. Runs continuously in background
2. Processes `batch_size` products per cycle
3. Waits 30 seconds between cycles
4. Saves progress after each cycle
5. Automatically resumes on restart

**UI Controls**: Settings tab → Auto-Enrichment section

**API Endpoints**:

```bash
# Start auto-enrichment
POST /api/enrich/auto/start?batch_size=10

# Stop auto-enrichment
POST /api/enrich/auto/stop

# Check status
GET /api/enrich/auto/status

# Reset position
POST /api/enrich/auto/reset
```

## State Persistence Benefits

### ✅ Resume After Interruption
- Browser crashes don't lose progress
- Can stop and resume anytime
- Backend restarts preserve position

### ✅ Incremental Processing
- Process in small batches
- Spread workload over time
- No need to complete in one session

### ✅ Progress Tracking
- See cumulative enriched/failed counts
- Monitor total progress across multiple runs
- Know exactly where you are in the queue

### ✅ Flexible Scheduling
- Run during lunch breaks
- Process overnight batches
- Resume next day from exact position

## File Locations

| Feature | State File | Location |
|---------|------------|----------|
| Leonteq PDF | `leonteq_enrich_state.json` | `data/` |
| Auto-Enrichment | `auto_enrich_state.json` | `data/` |

## Best Practices

### Leonteq PDF Enrichment

**Recommended Workflow**:
1. Run with `limit=50` first time
2. Check how many succeeded
3. Run again with `limit=50` - continues from offset 50
4. Repeat until all products processed
5. Reset when you want to re-enrich from start

**When to Reset**:
- After fixing parser issues (want to re-process products)
- After filter mode changes (different product set)
- When starting fresh enrichment campaign

### Auto-Enrichment

**Recommended Usage**:
1. Set `batch_size=10` for normal background processing
2. Start and leave running
3. Check progress periodically via UI
4. Stop when desired coverage reached
5. Resume anytime to continue

**When to Reset**:
- Cleared database and re-imported products
- Want to re-enrich all products with updated logic
- Starting fresh after data quality fixes

## Technical Implementation

### State Loading

```python
# Leonteq
from backend.app.services.leonteq_pdf_enrichment import load_leonteq_state

state = load_leonteq_state()
offset = state.get("offset", 0)  # Resume from saved position

# Auto-enrichment
from backend.app.services.auto_enrichment import AutoEnrichmentState

state = AutoEnrichmentState().load()
offset = state.finanzen_offset
```

### State Saving

```python
# Leonteq - saves every 5 products
save_leonteq_state(
    offset=current_offset,
    total_enriched=total_enriched,
    total_failed=total_failed
)

# Auto-enrichment - saves after each cycle
auto_enrich_state.finanzen_offset += batch_size
auto_enrich_state.save()
```

### State Reset

```python
# Leonteq
reset_leonteq_state()  # Deletes state file

# Auto-enrichment
auto_enrich_state.reset()  # Resets to offset=0
```

## Monitoring Progress

### Via Web UI

**Leonteq PDF Enrichment**:
- Currently: Manual check via logs
- Future: Add UI status indicator

**Auto-Enrichment**:
- Settings tab shows real-time stats
- Updates every 5 seconds
- Shows: offset, enriched, failed, progress %, remaining

### Via API

```bash
# Check Leonteq status
curl http://localhost:8000/api/enrich/leonteq/status

# Check auto-enrichment status
curl http://localhost:8000/api/enrich/auto/status
```

### Via Logs

```
INFO: Resuming from saved offset: 150 products already processed
INFO: [1/50] Processing Barrier Reverse Convertible (CH1234567890)
INFO: [2/50] Processing Express Certificate (CH0987654321)
...
INFO: Batch enrichment complete: {'processed': 50, 'enriched': 33, 'failed': 17}
INFO: Position saved: will resume from offset 200 on next run
```

## Troubleshooting

### "Offset seems wrong"

**Cause**: State file might be corrupted

**Solution**:
```bash
# Reset to start fresh
curl -X POST http://localhost:8000/api/enrich/leonteq/reset
# or
curl -X POST http://localhost:8000/api/enrich/auto/reset
```

### "Enrichment not resuming"

**Check**:
1. Verify state file exists: `ls -l data/*state.json`
2. Check file contents: `cat data/leonteq_enrich_state.json`
3. Check logs for "Resuming from saved offset" message

**Solution**: If state file is missing or invalid, it will auto-create and start from 0

### "Want to re-process already enriched products"

**Solution**: Reset state to start from beginning
```bash
# Leonteq
curl -X POST http://localhost:8000/api/enrich/leonteq/reset

# Auto-enrichment
curl -X POST http://localhost:8000/api/enrich/auto/reset
```

## Future Enhancements

- [ ] Add Leonteq to auto-enrichment (requires session persistence)
- [ ] UI buttons to check/reset Leonteq state
- [ ] Progress bars showing position in total queue
- [ ] Estimated time remaining calculations
- [ ] Email notifications when enrichment completes

## Summary

**State persistence makes enrichment practical for large datasets**:

✅ Process thousands of products incrementally
✅ Resume after any interruption
✅ Track cumulative progress across sessions
✅ No need to complete in one sitting
✅ Flexible, interruptible workflow

**Just run enrichment, stop when needed, resume anytime - your progress is always saved!**
