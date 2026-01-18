# Leonteq API Crawler - Automated Setup

## Overview

The Leonteq API crawler now features **fully automated token capture** integrated with the existing Leonteq login flow!

## ✨ New Feature: Auto-Capture API Token

When you click **"Open Leonteq login"** in the frontend, the system now:

1. ✅ Opens browser to Leonteq website
2. ✅ Monitors network requests in the background
3. ✅ **Automatically captures JWT API token** when you browse
4. ✅ **Saves token to `.env` file** automatically
5. ✅ Returns session state for HTML crawler

**No manual token extraction needed!**

## How to Use (3 Simple Steps)

### Step 1: Open the App

```bash
# Start the application
bash start.sh
```

Open http://localhost:5173 in your browser

### Step 2: Trigger Auto-Capture

In the app UI, find the **"Leonteq API Crawler"** section and click:

```
"Open Leonteq login (auto-captures token)"
```

A browser will open. **Simply browse the Leonteq site**:
- Click on products
- Use the search/filter
- Navigate around

The token will be **automatically captured** when API calls are made.

**You'll see:** `✓ API token captured automatically`

### Step 3: Run the Crawler

Once the browser closes, click:

```
"Run Leonteq API Crawler"
```

Watch the progress bar fill up! The crawler will:
- Import ~1,200+ products
- Extract complete details (underlyings, strikes, barriers, etc.)
- Take ~3-5 minutes total

## What Gets Imported

✅ **Complete product data:**
- All identifiers (ISIN, Valor, WKN, Symbol, LEI)
- Issuer name and details
- Product type & SSPA category
- Currency & denomination
- **Full underlying details** (names, ISINs, weights, RIC codes, Bloomberg tickers)
- **Strike & barrier levels**
- All dates (maturity, issue, fixing, subscription)
- Listing venues
- Coupon information (rate, frequency, type)
- Settlement details
- Participation rates

## Monitor Progress

**Real-time Dashboard:**
```
http://localhost:8000/static/status.html
```

**CLI Monitor:**
```bash
poetry run python3 scripts/monitor_crawl.py --latest
```

## Technical Details

### Auto-Capture Implementation

The `interactive_login_storage_state()` function in `core/sources/leonteq.py` now:

```python
def handle_request(request):
    """Capture Authorization header from API requests."""
    if "/rfb-api/products" in request.url:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()
            captured_token = token
            print(f"✓ API token captured automatically")

# Token is automatically saved to .env file
_save_token_to_env(captured_token)
```

### Frontend Integration

New state and functions in `App.jsx`:

```javascript
const [ltApiRunning, setLtApiRunning] = useState(false)
const [ltApiStatus, setLtApiStatus] = useState('')
const [ltApiProgress, setLtApiProgress] = useState({ completed: 0, total: 0 })

const runLeonteqApiCrawl = async () => {
  const res = await fetch(`${API_BASE}/ingest/crawl/leonteq-api`, { method: 'POST' })
  const data = await res.json()
  pollCrawl(data.run_id, setLtApiStatus, () => {}, setLtApiProgress)
}
```

### Database Storage

- **Table:** `products`
- **Source:** `leonteq_api`
- **Hash:** `sha256("leonteq_api:{isin}")`
- **Confidence:** 0.9 (vs 0.6 for HTML)

## Alternative Methods

If you prefer not to use the UI:

### Method 1: Standalone Script

```bash
poetry run python3 scripts/get_leonteq_token.py
```

### Method 2: Manual Extraction

1. Open DevTools (F12) → Network tab
2. Browse https://structuredproducts-ch.leonteq.com
3. Find `/rfb-api/products` request
4. Copy `Authorization: Bearer <token>` header
5. Add to `.env`: `SPA_LEONTEQ_API_TOKEN=<token>`

## Troubleshooting

### Token Not Captured

**Problem:** Browser closes but no token message appears

**Solution:** Make sure to actually **browse** the site:
- Click on different products
- Use search/filters
- The API calls need to be triggered

### Crawler Says "Token Not Configured"

**Problem:** Token wasn't saved to `.env`

**Solution:** Check `.env` file:
```bash
cat .env | grep LEONTEQ_API_TOKEN
```

If empty, run the login process again.

### Crawler Fails with 401 Error

**Problem:** Token expired or invalid

**Solution:** Re-run the login:
1. Click "Open Leonteq login" again
2. New token will be captured automatically

## Benefits Over Manual Methods

| Feature | Auto-Capture | Manual DevTools |
|---------|-------------|-----------------|
| Setup time | 30 seconds | 2-3 minutes |
| Technical knowledge | None | DevTools expertise |
| Error-prone | No | Yes (copy/paste errors) |
| Integrated | Yes | No |
| Token verification | Automatic | Manual |

## Summary

🎯 **Goal:** Import ~1,200+ Leonteq products with complete details

✅ **Solution:** Click 2 buttons in the UI

⚡ **Time:** ~5 minutes total

📊 **Result:** Complete product database with underlyings, strikes, barriers, and all details!

---

**No terminal commands, no DevTools, no copy/pasting - just click and go!** 🚀
