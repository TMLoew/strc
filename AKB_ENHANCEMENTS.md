# AKB Finanzportal Parser Enhancements

## Overview

Enhanced the AKB Finanzportal HTML parser to extract **significantly more data** from product detail pages.

## What Was Added

### 1. Barrier Level Extraction (Enhanced)

**Previous**: Basic barrier extraction with limited field names
**Now**: Comprehensive barrier extraction with multiple field variations

**New field names searched**:
- "Barriere"
- "Barrier"
- "Barriere Level"
- "Barriére"
- "Knock-In"

**Smart value detection**:
- Detects if value is **percentage** (≤100 or contains '%')
- Detects if value is **absolute price**
- Stores in appropriate field (`barrier_pct_of_initial` vs `barrier_level`)

**Example**:
```
Barriere: 60% → Stored as barrier_pct_of_initial = 60.0
Barrier: 1250.50 → Stored as barrier_level = 1250.50
```

### 2. Strike Price Extraction (NEW!)

**Field names**:
- "Strike"
- "Ausübungspreis" (German: Exercise price)
- "Basispreis" (German: Base price)
- "Strike Level"

**Stored as**: `underlyings[0].strike_level`

**Example**:
```html
<th>Strike</th>
<td>65.00 CHF</td>
```
→ `strike_level: {value: 65.0, confidence: 0.7, source: "akb_finanzportal"}`

### 3. Cap Level Extraction (NEW!)

**Field names**:
- "Cap"
- "Höchstbetrag" (German: Maximum amount)
- "Maximum"

**Smart detection**:
- Values ≤500 or containing '%' treated as percentages
- Stored in new `cap_level_pct` field

**Example**:
```html
<th>Cap</th>
<td>120%</td>
```
→ `cap_level_pct: {value: 120.0, confidence: 0.7}`

### 4. Participation Rate Extraction (NEW!)

**Field names**:
- "Partizipation" (German)
- "Partizipationsrate" (German)
- "Participation"
- "Participation Rate"

**Stored as**: `participation_rate_pct`

**Example**:
```html
<th>Partizipation</th>
<td>100%</td>
```
→ `participation_rate_pct: {value: 100.0, confidence: 0.7}`

### 5. Early Redemption / Payment Dates from Tables (ENHANCED!)

**Previous**: Basic date extraction
**Now**: Comprehensive table parsing for observation/payment schedules

**Detects tables with headers containing**:
- "Coupon" / "Zahlung" / "Payment" → Coupon payment schedule
- "Beobachtung" / "Observation" / "Autocall" / "Rückzahlung" → Early redemption dates

**Example HTML**:
```html
<table>
  <tr>
    <th>Beobachtungstag</th>
    <th>Rückzahlung</th>
  </tr>
  <tr>
    <td>15.06.2025</td>
    <td>100%</td>
  </tr>
  <tr>
    <td>15.12.2025</td>
    <td>100%</td>
  </tr>
  <tr>
    <td>15.06.2026</td>
    <td>100%</td>
  </tr>
</table>
```

→ Extracts all dates and stores as `call_observation_dates`

**Safety limits**:
- Maximum 50 dates per table (sanity check)
- Stores first 20 dates (prevents data overflow)
- Only dates that parse successfully

## New Model Fields

Added to [core/models/normalized.py](core/models/normalized.py):

```python
cap_level_pct: Field[float] = Field()
participation_rate_pct: Field[float] = Field()
```

These integrate seamlessly with existing underlyings fields.

## Data Quality Improvement

### Before Enhancement

```json
{
  "isin": {"value": "CH1505582432"},
  "product_type": {"value": "Barrier Reverse Convertible"},
  "coupon_rate_pct_pa": {"value": 8.5},
  "underlyings": [{"name": {"value": "Nestlé SA"}}]
}
```

### After Enhancement

```json
{
  "isin": {"value": "CH1505582432"},
  "product_type": {"value": "Barrier Reverse Convertible"},
  "coupon_rate_pct_pa": {"value": 8.5},
  "cap_level_pct": {"value": 120.0, "source": "akb_finanzportal"},
  "participation_rate_pct": {"value": 100.0, "source": "akb_finanzportal"},
  "underlyings": [
    {
      "name": {"value": "Nestlé SA"},
      "barrier_pct_of_initial": {"value": 60.0, "source": "akb_finanzportal"},
      "strike_level": {"value": 65.0, "source": "akb_finanzportal"}
    }
  ],
  "call_observation_dates": [
    {"value": "2025-06-15", "source": "akb_finanzportal"},
    {"value": "2025-12-15", "source": "akb_finanzportal"},
    {"value": "2026-06-15", "source": "akb_finanzportal"}
  ]
}
```

## Expected Impact

### Current AKB Data (8,319 products)

**Fields that should improve**:

| Field | Before | After (Estimated) | Improvement |
|-------|--------|-------------------|-------------|
| Barrier Level | ~8% (698) | 30-50% (2,500-4,000) | +300-500% |
| Strike Price | 0% (0) | 15-25% (1,200-2,000) | NEW |
| Cap Level | 0% (0) | 10-20% (800-1,600) | NEW |
| Participation Rate | 0% (0) | 15-25% (1,200-2,000) | NEW |
| Early Redemption Dates | Already good | Enhanced accuracy | Better quality |

**Why not 100%?**
- Many products don't have these features (warrants, trackers, plain vanilla bonds)
- Some HTML pages may have different table structures
- Field names may vary by issuer

**Products most likely to benefit**:
- Barrier Reverse Convertibles (1,332 products)
- Express Certificates (119 products)
- Autocallables (various types)

## How to Apply

### Option 1: Re-crawl AKB Products

**Re-run the AKB Portal crawler** to re-process existing products:

```bash
# Via UI
1. Open http://localhost:5173
2. Go to Ingest tab
3. Click "Run AKB Portal Crawler"

# Via CLI
poetry run python -c "
from backend.app.services.akb_portal_service import crawl_akb_portal_catalog
crawl_akb_portal_catalog()
"
```

This will:
- Re-fetch HTML for all products (using cached HTML where available)
- Re-parse with enhanced parser
- Update database with new fields
- Preserve existing high-confidence data

**Time**: ~3-4 hours for 8,000+ products

### Option 2: Targeted Re-processing

**Re-process only products missing data**:

```python
# Create a script to re-process specific products
from core.sources.akb_finanzportal import parse_detail_html
from backend.app.db import models

# Get products with raw_text but missing barriers
products = models.list_products(source_kind="akb_finanzportal", limit=1000)

for product in products:
    if product.get("raw_text"):
        # Re-parse HTML
        parsed = parse_detail_html(product["raw_text"], product["id"])
        # Update database with new fields
        # ... (merge logic needed)
```

### Option 3: Wait for Natural Updates

**Existing products will be updated** as:
- Products mature and are replaced
- New products are added
- Database is rebuilt

## Testing

### Verify New Fields

```sql
-- Check strike price coverage
SELECT COUNT(*) as total,
       SUM(CASE WHEN json_extract(normalized_json, '$.underlyings[0].strike_level.value') IS NOT NULL THEN 1 ELSE 0 END) as with_strike
FROM products
WHERE source_kind = 'akb_finanzportal';

-- Check cap level coverage
SELECT COUNT(*) as total,
       SUM(CASE WHEN json_extract(normalized_json, '$.cap_level_pct.value') IS NOT NULL THEN 1 ELSE 0 END) as with_cap
FROM products
WHERE source_kind = 'akb_finanzportal';

-- Check participation rate coverage
SELECT COUNT(*) as total,
       SUM(CASE WHEN json_extract(normalized_json, '$.participation_rate_pct.value') IS NOT NULL THEN 1 ELSE 0 END) as with_participation
FROM products
WHERE source_kind = 'akb_finanzportal';

-- Sample products with new fields
SELECT isin,
       json_extract(normalized_json, '$.underlyings[0].strike_level.value') as strike,
       json_extract(normalized_json, '$.cap_level_pct.value') as cap,
       json_extract(normalized_json, '$.participation_rate_pct.value') as participation
FROM products
WHERE source_kind = 'akb_finanzportal'
  AND (strike IS NOT NULL OR cap IS NOT NULL OR participation IS NOT NULL)
LIMIT 10;
```

### Sample Product Inspection

```bash
# Fetch a sample product and inspect extracted data
curl "http://localhost:8000/api/products?source=akb_finanzportal&limit=1" | jq '.items[0].normalized_json' | jq .
```

## Files Modified

### Core Parser
**[core/sources/akb_finanzportal.py](core/sources/akb_finanzportal.py)**
- Enhanced barrier extraction (lines 198-220)
- Added strike price extraction (lines 224-233)
- Added cap level extraction (lines 235-242)
- Added participation rate extraction (lines 244-253)
- Enhanced table parsing for dates (lines 255-290)

### Data Model
**[core/models/normalized.py](core/models/normalized.py)**
- Added `cap_level_pct: Field[float]` (line 97)
- Added `participation_rate_pct: Field[float]` (line 98)

## Backwards Compatibility

✅ **Fully backwards compatible**
- Existing products unchanged
- New fields are optional (Field() allows None)
- No database migration needed
- Old parsers continue to work

## Summary

✅ **Enhanced AKB parser** extracts:
- ✅ Barrier levels (multiple formats)
- ✅ Strike prices (NEW!)
- ✅ Cap levels (NEW!)
- ✅ Participation rates (NEW!)
- ✅ Early redemption dates (enhanced)

✅ **Expected improvement**: 300-500% more data coverage for structured product features

✅ **Ready to use**: Re-run AKB crawler to apply enhancements to 8,319 products

🎯 **Next step**: Run AKB Portal Crawler from UI or CLI to re-process products with enhanced parser
