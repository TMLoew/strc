# Monitoring Leonteq Imports - Complete Guide

This guide shows you how to monitor and view your Leonteq product imports in real-time.

---

## 🔍 Quick Monitor Commands

### **Monitor Latest Import**
```bash
cd "/Applications/Structured Products Analysis"
source .venv/bin/activate
python scripts/monitor_crawl.py --latest
```

### **Monitor Specific Crawl**
```bash
# Get the run_id from the API response when you start a crawl
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api
# Returns: {"run_id": "abc-123-def"}

# Monitor it
python scripts/monitor_crawl.py abc-123-def
```

### **View Recent Crawls**
```bash
python scripts/monitor_crawl.py --list
```

### **Show Statistics**
```bash
python scripts/monitor_crawl.py --stats
```

---

## 📊 Monitoring Options

### 1. **Real-Time Terminal Monitor**

**Command:**
```bash
python scripts/monitor_crawl.py --latest
```

**Output:**
```
Monitoring crawl: abc-123-def
Press Ctrl+C to stop monitoring

🔄 Crawl: leonteq_api (ID: abc-123-...)
   Status: RUNNING
   Progress: 45/1234 (3.6%)
   Elapsed: 12.3s
   ETA: 5.2m
   Rate: 3.7 products/sec
```

**Features:**
- Real-time progress updates
- ETA calculation
- Processing rate
- Error count

---

### 2. **API Status Endpoint**

**Check via API:**
```bash
# Get the run_id when starting crawl
RESPONSE=$(curl -s -X POST http://localhost:8000/api/ingest/crawl/leonteq-api)
RUN_ID=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

# Monitor status
watch -n 2 "curl -s http://localhost:8000/api/ingest/crawl/status/$RUN_ID | python -m json.tool"
```

**Response:**
```json
{
  "id": "abc-123-def",
  "name": "leonteq_api",
  "status": "running",
  "total": 1234,
  "completed": 45,
  "errors_count": 2,
  "last_error": null,
  "started_at": "2026-01-18T12:00:00",
  "updated_at": "2026-01-18T12:01:23",
  "ended_at": null
}
```

---

### 3. **Database Queries**

**Direct SQLite queries:**
```bash
sqlite3 data/structured_products.db "
  SELECT * FROM crawl_runs
  WHERE name = 'leonteq_api'
  ORDER BY started_at DESC
  LIMIT 5;
"
```

**Count imported products:**
```bash
sqlite3 data/structured_products.db "
  SELECT COUNT(*) FROM products
  WHERE source_kind = 'leonteq_api';
"
```

---

## 📦 Viewing Imported Products

### **View Latest Products**

```bash
python scripts/view_products.py --latest 10
```

**Output:**
```
================================================================================
Product ID: abc-123
Source: leonteq_api
Created: 2026-01-18T12:00:00
================================================================================

📋 Identification:
   ISIN: CH1234567890 (conf: 0.90, src: leonteq_api)
   Valor: 12345678 (conf: 0.90, src: leonteq_api)

🏦 Issuer & Type:
   Issuer: Leonteq Securities AG (conf: 0.80, src: leonteq_api)
   Type: Barrier Reverse Convertible (conf: 0.80, src: leonteq_api)

💰 Financial:
   Currency: CHF (conf: 0.90, src: leonteq_api)
   Coupon Rate: 8.5 (conf: 0.80, src: leonteq_api)

📅 Dates:
   Settlement: 2026-01-20 (conf: 0.80, src: leonteq_api)
   Maturity: 2027-01-20 (conf: 0.90, src: leonteq_api)

📊 Underlyings:
   1. SMI (conf: 0.80, src: leonteq_api)
      Strike: 11500.0 (conf: 0.70, src: leonteq_api)
      Barrier: 9200.0 (conf: 0.70, src: leonteq_api)
```

---

### **View by Source**

```bash
# View Leonteq API products
python scripts/view_products.py --source leonteq_api --limit 5

# View AKB products
python scripts/view_products.py --source akb_html --limit 5
```

---

### **Search Products**

```bash
# By ISIN
python scripts/view_products.py --isin CH1234567890

# By search term
python scripts/view_products.py --search "Leonteq"
python scripts/view_products.py --search "SMI"
```

---

### **Database Statistics**

```bash
python scripts/view_products.py --stats
```

**Output:**
```
📊 Database Statistics

================================================================================

Total Products: 1,234

By Source:
   leonteq_api         :  1,000 ( 81.0%)
   akb_html            :    150 ( 12.2%)
   leonteq_html        :     84 (  6.8%)

Top 10 Issuers:
   Leonteq Securities AG          :    450
   UBS AG                         :    200
   Credit Suisse AG               :    150

By Currency:
   CHF       :    900
   EUR       :    200
   USD       :    134

Recent Imports (last 7 days):
   2026-01-18:  1,000 products
   2026-01-17:    150 products
```

---

## 🔧 Advanced Monitoring

### **Monitor in Browser**

Open the API docs and use the interactive endpoint:

```
http://localhost:8000/docs#/ingest/crawl_status_ingest_crawl_status__run_id__get
```

---

### **Custom Monitoring Script**

```python
#!/usr/bin/env python3
import requests
import time

run_id = "YOUR_RUN_ID_HERE"
api_url = f"http://localhost:8000/api/ingest/crawl/status/{run_id}"

while True:
    response = requests.get(api_url)
    data = response.json()

    if 'error' in data:
        print(f"Error: {data['error']}")
        break

    status = data['status']
    completed = data['completed']
    total = data['total']
    percentage = (completed / total * 100) if total > 0 else 0

    print(f"\rProgress: {completed}/{total} ({percentage:.1f}%) - Status: {status}", end="")

    if status in ['completed', 'failed']:
        print(f"\n\nCrawl {status}!")
        break

    time.sleep(2)
```

---

## 📈 Live Monitoring While Crawling

### **Step 1: Start the Crawl**

```bash
# Terminal 1: Start the backend
cd "/Applications/Structured Products Analysis"
bash start.sh
```

```bash
# Terminal 2: Start the crawl
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api
# Returns: {"run_id": "abc-123-def"}
```

---

### **Step 2: Monitor in Real-Time**

**Option A: CLI Monitor**
```bash
# Terminal 3: Monitor progress
python scripts/monitor_crawl.py abc-123-def
```

**Option B: Watch Command**
```bash
# Terminal 3: Watch API status
watch -n 1 "curl -s http://localhost:8000/api/ingest/crawl/status/abc-123-def | python -m json.tool | grep -E 'status|completed|total|errors'"
```

**Option C: Backend Logs**
```bash
# Terminal 3: Watch backend logs
tail -f output/logs/backend.log | grep -i leonteq
```

---

### **Step 3: View Results**

After crawl completes:

```bash
# View imported products
python scripts/view_products.py --source leonteq_api --latest 10

# Show statistics
python scripts/view_products.py --stats
```

---

## 🎯 Complete Workflow Example

### **1. Start Import**

```bash
# Start backend (if not running)
bash start.sh

# In another terminal, start crawl
cd "/Applications/Structured Products Analysis"
source .venv/bin/activate

# Start crawl and capture run_id
RUN_ID=$(curl -s -X POST http://localhost:8000/api/ingest/crawl/leonteq-api | python -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

echo "Started crawl: $RUN_ID"
```

---

### **2. Monitor Progress**

```bash
# Monitor in real-time
python scripts/monitor_crawl.py $RUN_ID
```

**You'll see:**
```
Monitoring crawl: abc-123-def
Press Ctrl+C to stop monitoring

🔄 Crawl: leonteq_api (ID: abc-123-...)
   Status: RUNNING
   Progress: 234/1234 (19.0%)
   Errors: 3
   Elapsed: 1.2m
   ETA: 5.3m
   Rate: 3.2 products/sec

✅ Crawl: leonteq_api (ID: abc-123-...)
   Status: COMPLETED
   Progress: 1234/1234 (100.0%)
   Errors: 5
   Duration: 6.5m

Crawl finished!
```

---

### **3. View Results**

```bash
# Show statistics
python scripts/view_products.py --stats

# View latest products
python scripts/view_products.py --source leonteq_api --limit 10

# Search for specific product
python scripts/view_products.py --search "SMI"
```

---

## 📋 Quick Reference

| Task | Command |
|------|---------|
| **Monitor latest crawl** | `python scripts/monitor_crawl.py --latest` |
| **Monitor specific crawl** | `python scripts/monitor_crawl.py <run_id>` |
| **List recent crawls** | `python scripts/monitor_crawl.py --list` |
| **Show DB statistics** | `python scripts/monitor_crawl.py --stats` |
| **View latest products** | `python scripts/view_products.py --latest 10` |
| **View by source** | `python scripts/view_products.py --source leonteq_api` |
| **View specific ISIN** | `python scripts/view_products.py --isin CH1234567890` |
| **Search products** | `python scripts/view_products.py --search "Leonteq"` |
| **Product statistics** | `python scripts/view_products.py --stats` |

---

## 🛠️ Troubleshooting

### **Monitor shows "Crawl not found"**

**Check if crawl exists:**
```bash
python scripts/monitor_crawl.py --list
```

---

### **No products showing up**

**Check database:**
```bash
sqlite3 data/structured_products.db "SELECT COUNT(*) FROM products WHERE source_kind='leonteq_api';"
```

**Check crawl errors:**
```bash
sqlite3 data/structured_products.db "SELECT last_error FROM crawl_runs WHERE name='leonteq_api' ORDER BY started_at DESC LIMIT 1;"
```

---

### **Backend not responding**

**Check if backend is running:**
```bash
curl http://localhost:8000/docs
```

**Check backend logs:**
```bash
tail -f output/logs/backend.log
```

---

## 💡 Tips

1. **Use `--latest` for quick monitoring** - No need to copy run_id
2. **Keep terminal open during import** - See real-time progress
3. **Check stats after import** - Verify all products imported
4. **Search by ISIN** - Find specific products quickly
5. **Monitor errors** - Check `errors_count` in status

---

Happy monitoring! 📊
