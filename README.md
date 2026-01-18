# Structured Products Analysis

Local-first tool to ingest, normalize, analyze, and compare structured products from multiple sources.

## Features

### Data Collection
- **Leonteq API Crawler**: Automated discovery of 5,000+ structured products from Leonteq's authenticated API
- **AKB Finanzportal Crawler**: Comprehensive catalog scraping with 12,000+ products
- **Swissquote Scanner**: Market data enrichment with real-time pricing
- **Finanzen.ch Enrichment**: Coupon rates, barriers, and structured data extraction via browser automation
- **PDF Termsheet Parsing**: Extract complete product terms from Leonteq PDFs

### Data Enrichment
- **Smart Filtering**: Target products missing specific data (coupons, barriers, etc.)
- **Multi-Source Merging**: Intelligent field-level merging with confidence scoring
- **Coupon Coverage**: Improve from 2.6% to 70-80% coverage with finanzen.ch crawler
- **Progress Tracking**: Real-time progress bars with checkpoint/resume capability

### Analysis & Comparison
- **Best-of-Each-Field Mode**: Automatically select highest-confidence data across sources
- **Advanced Filtering**: Filter by issuer, currency, rating, yield, coupon, barrier, issue date
- **Multi-Type Search**: Search by ISIN, Valor (6-9 digits), or Symbol/Ticker
- **Risk Decomposition**: Automated payoff structure analysis and component breakdown
- **Side-by-Side Comparison**: Compare multiple products with highlighting

### Data Quality
- **Confidence Scoring**: Track data source reliability (0.6-0.9 scale)
- **Source Attribution**: Full traceability with excerpts and timestamps
- **Deduplication**: SHA-256 hashing prevents duplicate products
- **Audit Trail**: Complete history of data updates and enrichments

## Quick start

### 🚀 Launch from Desktop (macOS)

**Double-click** `Structured Products.app` in the Applications folder!

The app will:
- Start the backend server (http://localhost:8000)
- Launch the frontend (http://localhost:5173)
- Open in Terminal with logs

> **First time setup:** See [Installation](#installation) below

### 📟 Command Line

1) Create a virtualenv and install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install poetry
poetry install
```

2) Run backend only

```bash
poetry run python -m backend.app.main
```

3) Run backend + frontend (one command)

```bash
bash start.sh
# OR
make dev-all
```

4) Run CLI ingest

```bash
poetry run python scripts/spa.py ingest
```

## Installation

### Initial Setup

1. **Clone or extract** to `/Applications/Structured Products Analysis/`

2. **Install Python dependencies:**
   ```bash
   cd "/Applications/Structured Products Analysis"
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip poetry
   poetry install
   ```

3. **Install Node.js dependencies (for frontend):**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (API tokens, etc.)
   ```

5. **Launch the app:**
   - Double-click `Structured Products.app`, OR
   - Run `bash start.sh` from Terminal

### Verify Installation

After launching, verify:
- Backend API: http://localhost:8000/docs
- Frontend UI: http://localhost:5173

## Documentation

### Quick Start Guides
- **[QUICKSTART_COUPONS.md](QUICKSTART_COUPONS.md)** - Get coupon data in 5 minutes
- **[INSTALL.md](INSTALL.md)** - Detailed installation instructions

### Feature Documentation
- **[FINANZEN_CRAWLER.md](FINANZEN_CRAWLER.md)** - Complete finanzen.ch crawler documentation
- **[MISSING_DATA_SOLUTION.md](MISSING_DATA_SOLUTION.md)** - Solving the missing coupon problem
- **[ENRICHMENT_COMPLETE.md](ENRICHMENT_COMPLETE.md)** - Data enrichment system overview
- **[MONITORING.md](MONITORING.md)** - Real-time import monitoring

### API & Integration
- **[LEONTEQ_API_SETUP.md](LEONTEQ_API_SETUP.md)** - Leonteq API configuration
- **[PARSER_ISSUES.md](PARSER_ISSUES.md)** - Known parsing challenges

## Repo layout

- `input/` - Drop PDFs here for processing
- `not_reviewed_yet/` - Processed but not validated
- `reviewed/` - Validated products
- `to_be_signed/` - Needs attention
- `output/parsed/` - Parsed JSON artifacts
- `data/` - SQLite database and cache files
- `frontend/` - React web UI
- `backend/` - FastAPI server
- `core/` - Core parsing and normalization logic
- `scripts/` - CLI tools for enrichment and analysis

## Data Sources & Crawlers

> 📊 **[See MONITORING.md for how to view imports in real-time](MONITORING.md)**

### Leonteq API Crawler

Discovers and ingests all structured products from Leonteq's authenticated `/rfb-api/products` API endpoint.

**Configuration (.env file):**
```bash
SPA_LEONTEQ_API_TOKEN=<JWT_Bearer_Token>  # Required: Copy from browser DevTools
SPA_ENABLE_LEONTEQ_API_CRAWL=True          # Enable/disable crawler
SPA_LEONTEQ_API_PAGE_SIZE=50               # Results per page (max 50)
SPA_LEONTEQ_API_MAX_PRODUCTS=100           # Optional: limit for testing (omit for full crawl)
SPA_LEONTEQ_API_RATE_LIMIT_MS=100          # Delay between API calls (ms)
```

**How to get JWT token:**

**Option 1: Automated (Recommended)**
```bash
python3 scripts/get_leonteq_token.py
```
This script will:
1. Open a browser to Leonteq website
2. Wait for you to browse the site (triggering API calls)
3. Automatically capture the JWT token from network requests
4. Save it to your `.env` file
5. Verify the token works

**Option 2: Manual**
1. Open Leonteq site in browser: https://structuredproducts-ch.leonteq.com
2. Open DevTools (F12) → Network tab
3. Find any `/rfb-api/products` request
4. Copy the `Authorization: Bearer <token>` header value
5. Set `SPA_LEONTEQ_API_TOKEN=<token>` in `.env` file

**API Endpoint:**
```bash
# Start crawler (background task)
curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api

# Returns: {"run_id": "uuid"}

# Poll status
curl http://localhost:8000/api/ingest/crawl/status/{run_id}

# Returns: {"status": "running"|"completed"|"failed", "total": 1234, "completed": 150, "errors_count": 2}
```

**Features:**
- Paginated discovery (50 products per page)
- Parallel processing with ThreadPoolExecutor
- Progress tracking in `crawl_runs` table
- Extracts comprehensive data: ISIN, Valor, type, issuer, dates, venues, strike/barrier levels
- Deduplication via `source_file_hash_sha256`
- High confidence scores (0.9) for API data vs 0.6-0.8 for HTML parsing
- No PDF downloads (API data only)

**Data stored:**
- Database table: `products`
- Source kind: `leonteq_api`
- Deduplication hash: `sha256("leonteq_api:{isin}")`
- Raw API JSON stored in `raw_text` column

### AKB Catalog Crawler

Discovers ISINs from the AKB public catalog page and stores minimal product data.

**Features:**
- Scrapes public HTML catalog: https://www.akb.ch/firmen/anlagen/anlageprodukte/strukturierte-produkte
- Extracts ISINs using regex pattern matching
- Background task execution with progress tracking
- Parallel processing with ThreadPoolExecutor
- Caching with versioned archiving

**API Endpoint:**
```bash
# Start crawler (background task)
curl -X POST http://localhost:8000/api/ingest/crawl/akb

# Returns: {"run_id": "uuid"}

# Poll status
curl http://localhost:8000/api/ingest/crawl/status/{run_id}
```

**Data stored:**
- Database table: `products`
- Source kind: `akb_html`
- Deduplication hash: `sha256("akb:{isin}")`
- Confidence: 0.6 (catalog only provides ISIN)

---

### AKB Enrichment Crawler

Discovers ISINs from AKB catalog and enriches with multi-source data.

**Enrichment sources:**
1. **AKB Catalog** - ISIN extraction
2. **Leonteq** - HTML page scraping + PDF termsheet download + parsing
3. **Swissquote** - Quote page data
4. **Yahoo Finance** - Historical data (if `SPA_ENABLE_YAHOO_ENRICH=true`)

**API Endpoint:**
```bash
# Start enrichment crawler
curl -X POST http://localhost:8000/api/ingest/crawl/akb-enrich

# Returns: {"run_id": "uuid"}
```

**Features:**
- Parallel multi-source fetching
- Error collection per source (continues on failure)
- Progress tracking (total = ISINs × active sources)
- Automatic merging via database deduplication

**Configuration (.env file):**
```bash
SPA_ENABLE_YAHOO_ENRICH=false  # Enable/disable Yahoo Finance enrichment
SPA_CRAWL_MAX_WORKERS=10       # Parallel worker threads
```

---

### AKB Portal Crawler

Advanced crawler for AKB Finanzportal with detailed product search and parsing.

**Features:**
- Multi-search API integration
- Detailed product page parsing
- Extracts comprehensive fields: issuer, type, dates, denomination, EUSIPA category
- Enriches discovered products with Leonteq, Swissquote, Yahoo data

**API Endpoint:**
```bash
# Start portal crawler
curl -X POST http://localhost:8000/api/ingest/crawl/akb-portal

# Returns: {"run_id": "uuid"}
```

**Data stored:**
- Source kind: `akb_finanzportal`
- Deduplication hash: `sha256("akb_portal:{listing_id}")`
- High confidence fields (0.8-0.9): ISIN, Valor, issuer, maturity

**Configuration:**
```bash
SPA_ENABLE_PORTAL_CRAWL=true  # Enable/disable portal crawler
```

---

### Finanzen.ch Coupon Crawler

**Purpose**: Extract coupon rates and structured product data from finanzen.ch using browser automation.

**Why**: Solves the critical missing coupon problem (97.4% of products missing coupons).

**Quick Start**:
```bash
# Check what's missing
poetry run python scripts/check_missing_data.py

# Enrich 100 products with missing coupons
poetry run python scripts/enrich_finanzen.py --limit 100

# Or use Web UI at http://localhost:5173 → Settings tab
```

**Features**:
- Browser automation (bypasses 403 blocks)
- Extracts coupons, barriers, strikes, caps, participation rates
- Smart filtering (missing_coupon, missing_barrier, missing_any, all_with_isin)
- Progress tracking with checkpoints
- Resume capability after interruption

**Filter Modes**:
- `missing_coupon` - Only products without coupon rates (RECOMMENDED)
- `missing_barrier` - Only products without barrier levels
- `missing_any` - Products missing coupons OR barriers
- `all_with_isin` - All products with ISINs (refresh all)

**API Endpoint**:
```bash
curl -X POST "http://localhost:8000/api/enrich/finanzen-ch?limit=100&filter_mode=missing_coupon"

# Returns: {"processed": 100, "enriched": 62, "failed": 38}
```

**Expected Results**:
- Success rate: 60-80%
- Speed: 3-4 seconds per product
- Final coupon coverage: 70-80% (from 2.6%)

**Documentation**: [FINANZEN_CRAWLER.md](FINANZEN_CRAWLER.md), [QUICKSTART_COUPONS.md](QUICKSTART_COUPONS.md)

---

### Leonteq PDF Enrichment

**Purpose**: Extract comprehensive data from Leonteq termsheet PDFs for products missing critical fields.

**Features**:
- Extracts coupons (fixed and conditional)
- Extracts barrier levels (% or absolute)
- Extracts early redemption conditions
- Extracts autocall thresholds, strikes, caps, participation rates
- Smart filtering (only process products missing specific data)

**API Endpoint**:
```bash
curl -X POST "http://localhost:8000/api/enrich/leonteq-pdfs?limit=100&filter_mode=missing_any"

# Returns: {"processed": 100, "enriched": 75, "failed": 25}
```

**Filter Modes**:
- `missing_any` - Products missing coupons OR barriers (RECOMMENDED)
- `missing_coupon` - Only products without coupon rates
- `missing_barrier` - Only products without barrier levels
- `all` - All Leonteq API products

**Usage**: Via Web UI Settings tab or CLI script

---

### Other Crawlers

See [backend/app/api/routes_ingest.py](backend/app/api/routes_ingest.py) for:
- Swissquote scanner crawler
- PDF directory ingestion

## Troubleshooting

### Desktop App Won't Launch

**Problem:** Double-clicking `Structured Products.app` does nothing

**Solutions:**
1. **Check permissions:**
   ```bash
   chmod +x "Structured Products.app/Contents/MacOS/launch"
   ```

2. **Allow app in System Preferences:**
   - macOS may block unsigned apps
   - Go to System Preferences → Security & Privacy
   - Click "Open Anyway" if prompted

3. **Run from Terminal to see errors:**
   ```bash
   cd "/Applications/Structured Products Analysis"
   bash start.sh
   ```

### Virtual Environment Not Found

**Problem:** `Error: Virtual environment not found!`

**Solution:**
```bash
cd "/Applications/Structured Products Analysis"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip poetry
poetry install
```

### Port Already in Use

**Problem:** `Error: Port 8000 already in use`

**Solution:**
1. **Find and kill the process:**
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Or change the port** in `backend/app/main.py`

### Module Not Found Errors

**Problem:** `ModuleNotFoundError: No module named 'httpx'`

**Solution:**
```bash
source .venv/bin/activate
poetry install
```

### Leonteq API Token Invalid

**Problem:** `RuntimeError: leonteq_api_token_invalid`

**Solution:**
1. Open https://structuredproducts-ch.leonteq.com in browser
2. Open DevTools (F12) → Network tab
3. Find any `/rfb-api/products` request
4. Copy the `Authorization: Bearer <token>` header
5. Update `.env`:
   ```bash
   SPA_LEONTEQ_API_TOKEN=<your-token-here>
   ```

### Swissquote Login Browser Closes Immediately

**Problem:** Browser opens and immediately closes when trying to log in

**Solution:**
The login function now waits at least 10 seconds before checking login status. This gives you time to:
1. Enter credentials
2. Complete 2FA if required
3. Navigate to the scanner page

**What to expect:**
- Browser opens to Swissquote login page
- Log in manually (you have 5 minutes)
- Browser will automatically close after successful login
- Progress messages will show in Terminal

**If still having issues:**
```bash
# Test the login manually in Python
cd "/Applications/Structured Products Analysis"
source .venv/bin/activate
python3 << EOF
from core.sources.swissquote_scanner import interactive_login_storage_state
state = interactive_login_storage_state()
print("Success! Session captured.")
EOF
```

### Database Locked Errors

**Problem:** `database is locked`

**Solution:**
```bash
# Stop all running instances
pkill -f "backend.app.main"

# Remove lock file if exists
rm -f data/structured_products.db-shm
rm -f data/structured_products.db-wal

# Restart
bash start.sh
```

### Frontend Not Loading

**Problem:** Frontend shows blank page or connection error

**Solutions:**
1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/docs
   ```

2. **Reinstall frontend dependencies:**
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   npm run dev
   ```

3. **Clear browser cache** and reload

### Crawler Status Stuck at "running"

**Problem:** Crawler shows status "running" but no progress

**Solution:**
1. **Check backend logs:**
   ```bash
   tail -f output/logs/backend.log
   ```

2. **Query database directly:**
   ```bash
   sqlite3 data/structured_products.db "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT 5;"
   ```

3. **Restart crawler:**
   ```bash
   # Get the run_id from status endpoint
   curl http://localhost:8000/api/ingest/crawl/leonteq-api
   ```

## Web UI Features

### Products Tab

**Search**:
- Search by ISIN (e.g., CH1505582432)
- Search by Valor (6-9 digits, e.g., 123456)
- Search by Symbol/Ticker (e.g., AAPL, NESN)

**Filters**:
- **Source**: Filter by data source (Leonteq API, AKB, Swissquote, etc.)
- **Product Type**: Filter by product category (Barrier Reverse Convertible, etc.)
- **Issuer**: Filter by issuing bank
- **Currency**: Filter by denomination currency (CHF, USD, EUR, etc.)
- **Credit Rating**: Filter by issuer rating
- **WTY (Worst-to-Yield)**: Filter by yield ranges (<2%, 2-5%, 5-8%, 8%+)
- **YTM (Yield-to-Maturity)**: Filter by yield ranges
- **Coupon**: Filter by presence/absence of coupon data
- **Barrier**: Filter by presence/absence of barrier data
- **Issue Date**: Filter by recency (Missing Date, Future/Subscription Period, Last 3/6/12 months, Older than 12 months)

**Viewing Modes**:
- **Standard Mode**: Shows all products with applied filters
- **Best-of-Each-Field Mode**: Automatically merges data from multiple sources, selecting highest-confidence value for each field

**Product Actions**:
- Click product to view detailed breakdown
- Select multiple products for side-by-side comparison
- View risk decomposition and payoff structure analysis

### Statistics Tab

View comprehensive database statistics:
- Total products by source
- Data completeness metrics
- Missing data analysis
- Import history and trends

### Settings Tab

**PDF Enrichment**:
- Select filter mode (Missing Coupons, Missing Barriers, Missing Any, All)
- Set limit (number of products to process)
- Track progress with real-time progress bar
- View success/error counts

**Finanzen.ch Crawler**:
- Select filter mode (Missing Coupons, Missing Barriers, etc.)
- Set batch size
- Monitor enrichment progress
- Resume after interruption

**Clear Incomplete Products**:
- Remove products with insufficient data
- Configurable thresholds for what counts as "complete"

## Notes

- Credentials live in `.env` and are never committed
- Parsing is deterministic and unit-testable; raw excerpts are capped
- Logs are stored in `output/logs/`
- Database is at `data/structured_products.db`
- All crawlers support progress tracking and can be monitored in real-time
- Data enrichment uses confidence scoring to prefer higher-quality sources
- Multiple products with same ISIN are deduplicated via SHA-256 hashing
