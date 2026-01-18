# Installation Guide - Structured Products Analysis

## Quick Install (5 minutes)

### Step 1: Install Python Dependencies

```bash
cd "/Applications/Structured Products Analysis"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip poetry
poetry install
```

**Expected output:** Installation of ~50 packages (httpx, fastapi, pydantic, etc.)

---

### Step 2: Install Node.js Dependencies (Optional - for frontend)

```bash
cd frontend
npm install
cd ..
```

**Expected output:** Installation of React, Vite, and dependencies

---

### Step 3: Configure Environment

```bash
cp .env.example .env
```

**Edit `.env`** with your preferred text editor:
```bash
nano .env
# OR
open -e .env
```

**Minimum required settings:**
```bash
SPA_DATA_DIR=./data
SPA_DB_PATH=./data/structured_products.db
```

**Optional - for Leonteq API crawler:**
```bash
SPA_LEONTEQ_API_TOKEN=<your-jwt-token-here>
```

To get the Leonteq API token:
1. Visit https://structuredproducts-ch.leonteq.com
2. Open DevTools (F12) → Network tab
3. Find `/rfb-api/products` request
4. Copy the `Authorization: Bearer <token>` header value

---

### Step 4: Initialize Database

The database is created automatically on first run. Optionally create directories:

```bash
mkdir -p data input output/logs output/parsed output/exports
mkdir -p not_reviewed_yet reviewed to_be_signed
```

---

### Step 5: Launch Application

**Option A: Desktop App (macOS)**

Double-click `Structured Products.app`

**Option B: Command Line**

```bash
bash start.sh
```

---

## Verification

### 1. Check Backend is Running

Open browser: http://localhost:8000/docs

You should see the FastAPI Swagger documentation.

### 2. Check Frontend (if installed)

Open browser: http://localhost:5173

### 3. Test API Endpoint

```bash
curl http://localhost:8000/api/ingest/crawl/status/test
```

Expected: `{"error": "not_found"}` (this is correct - means API is responding)

---

## First Crawl

### Test Leonteq API Crawler

1. **Ensure token is configured** in `.env`:
   ```bash
   grep LEONTEQ_API_TOKEN .env
   ```

2. **Start a test crawl** (limited to 10 products):
   ```bash
   # Edit .env temporarily
   echo "SPA_LEONTEQ_API_MAX_PRODUCTS=10" >> .env

   # Trigger crawl
   curl -X POST http://localhost:8000/api/ingest/crawl/leonteq-api
   ```

3. **Get the run_id** from response:
   ```json
   {"run_id": "abc-123-def"}
   ```

4. **Poll status:**
   ```bash
   curl http://localhost:8000/api/ingest/crawl/status/abc-123-def
   ```

5. **Check results in database:**
   ```bash
   sqlite3 data/structured_products.db "SELECT COUNT(*) FROM products WHERE source_kind='leonteq_api';"
   ```

---

## Troubleshooting Installation

### Python Version Issues

**Problem:** `python3: command not found`

**Solution:**
Install Python 3.10+ from https://www.python.org/downloads/

Verify:
```bash
python3 --version
```

Should show: `Python 3.10.x` or higher

---

### Poetry Installation Fails

**Problem:** `pip install poetry` fails

**Solution:**
Use official installer:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Add to PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

### Node.js Not Found

**Problem:** `npm: command not found`

**Solution:**
Install Node.js from https://nodejs.org/ (LTS version)

Or via Homebrew:
```bash
brew install node
```

Verify:
```bash
node --version
npm --version
```

---

### Permission Denied

**Problem:** `Permission denied` when running scripts

**Solution:**
```bash
chmod +x start.sh
chmod +x "Structured Products.app/Contents/MacOS/launch"
```

---

### macOS Security Warning

**Problem:** macOS blocks the app: "cannot be opened because the developer cannot be verified"

**Solution:**
1. Right-click `Structured Products.app`
2. Select "Open"
3. Click "Open" in the dialog

Or via command line:
```bash
xattr -cr "Structured Products.app"
```

---

## Uninstallation

To completely remove the application:

```bash
cd "/Applications/Structured Products Analysis"

# Stop any running processes
pkill -f "backend.app.main"

# Remove virtual environment
rm -rf .venv

# Remove Node modules
rm -rf frontend/node_modules

# Remove data (optional - this deletes your database!)
rm -rf data

# Remove entire directory
cd /Applications
rm -rf "Structured Products Analysis"
```

---

## Next Steps

After installation:

1. **Read the main [README.md](README.md)** for usage instructions
2. **Configure crawlers** in `.env` (API tokens, etc.)
3. **Test each crawler:**
   - AKB Catalog: `POST /api/ingest/crawl/akb`
   - Leonteq API: `POST /api/ingest/crawl/leonteq-api`
   - AKB Portal: `POST /api/ingest/crawl/akb-portal`

4. **Explore the API docs:** http://localhost:8000/docs
5. **Check the database:**
   ```bash
   sqlite3 data/structured_products.db "SELECT source_kind, COUNT(*) FROM products GROUP BY source_kind;"
   ```

---

## Support

- **Issues:** Check [Troubleshooting](README.md#troubleshooting) in README.md
- **Logs:** `output/logs/backend.log`
- **Database:** `data/structured_products.db`

Happy analyzing! 📊
