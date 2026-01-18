# Parser Issues - Missing Product Details

## Summary

Most products in the database are missing critical details (underlyings, currency, full product information) because the HTML parsers are very basic and only extract minimal fields.

## Current Database State

```
Source              Count    Issuer  Currency  Type  Underlyings
----------------  -------  -------  ---------  ----  -----------
akb_finanzportal     1767      ✓        ✓       ✓        ✗
leonteq_html          127      ✗        ✓       ✗        ✗
swissquote_html      1046      ✗        ✗       ✗        ✗
leonteq_api             0    (not run yet - will have full data)
```

## Parser Status

### 1. Swissquote HTML Parser (`core/sources/swissquote.py`)

**Status**: ⚠️ CRITICAL - Only extracts ISIN

**Current extraction**:
- ✓ ISIN (confidence: 0.4)
- ✗ Issuer
- ✗ Currency
- ✗ Product Type
- ✗ Underlyings
- ✗ Dates
- ✗ Strike/Barrier levels

**Issue**: The `parse_quote_html()` function only extracts ISIN and returns immediately. No other fields are parsed from the HTML.

**Impact**: 1046 products with minimal data

**Fix needed**: Enhance parser to extract fields from Swissquote HTML structure

---

### 2. Leonteq HTML Parser (`core/sources/leonteq.py`)

**Status**: ⚠️ BROKEN - Extracts null values

**Current extraction**:
- ✓ ISIN (confidence: 0.8)
- ✓ Valor (confidence: 0.6) - if found
- ✓ Currency (confidence: 0.6) - if found
- ✗ Issuer (returns null)
- ✗ Product Type (returns null)
- ✗ Underlyings
- ✗ Dates (except Issue Date - if found)

**Issue**: The parser uses `_find_label_value()` to search for "Product Type:" and "Issuer:" labels in the HTML text, but these labels don't exist or have changed in the current HTML structure.

**Impact**: 127 products with currency but no other details

**Fix needed**: Update HTML parsing to match current Leonteq public page structure

---

### 3. AKB Finanzportal Parser (`core/sources/akb_finanzportal.py`)

**Status**: ✓ PARTIAL - Extracts basic info but no underlyings

**Current extraction**:
- ✓ ISIN
- ✓ Valor
- ✓ Issuer Name
- ✓ Product Type
- ✓ Currency
- ✗ Underlyings
- ✗ Strike/Barrier levels
- ✗ Detailed dates

**Impact**: 1767 products with basic info but missing underlyings

**Fix needed**: Enhance parser to extract underlying information

---

### 4. Leonteq API Parser (`core/sources/leonteq_api.py`)

**Status**: ✓ EXCELLENT - Comprehensive extraction

**Current extraction**:
- ✓ All identifiers (ISIN, Valor, WKN, Symbol, LEI)
- ✓ Issuer Name
- ✓ Product Type & SSPA Category
- ✓ Currency & Denomination
- ✓ All dates (maturity, issue, fixing, subscription)
- ✓ Listing venues
- ✓ Underlyings (full details including name, ISIN, RIC, Bloomberg, currency, weight)
- ✓ Strike & Barrier levels
- ✓ Coupon information
- ✓ Settlement details
- ✓ Participation rate

**Impact**: Not yet run - but will provide comprehensive data when configured

**Action needed**: User needs to configure `SPA_LEONTEQ_API_TOKEN` in `.env` file

---

## Recommended Actions

### Priority 1: Configure Leonteq API (Best Data Source)

The Leonteq API provides the most comprehensive data. To enable:

1. Open https://structuredproducts-ch.leonteq.com in browser
2. Open DevTools > Network tab
3. Find `/rfb-api/products` request
4. Copy the `Authorization: Bearer <token>` header value
5. Add to `.env` file:
   ```bash
   SPA_LEONTEQ_API_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
6. Test with: `python3 scripts/test_leonteq_api.py`
7. Run crawler: POST `/api/ingest/crawl/leonteq-api`

### Priority 2: Fix Swissquote Parser (1046 products affected)

Enhance `core/sources/swissquote.py` to extract more fields from the HTML structure.

**Complexity**: Medium - Requires analyzing Swissquote HTML structure

### Priority 3: Fix Leonteq HTML Parser (127 products affected)

Update `core/sources/leonteq.py` to match current HTML structure.

**Complexity**: Medium - Labels may have changed or moved to different elements

### Priority 4: Enhance AKB Parser (1767 products - underlyings missing)

Add underlying extraction to `core/sources/akb_finanzportal.py`.

**Complexity**: Medium-High - May require additional scraping

---

## Testing

After fixes, verify with:

```bash
# View sample products
python3 scripts/view_products.py --source swissquote_html --limit 3
python3 scripts/view_products.py --source leonteq_html --limit 3

# Check statistics
python3 scripts/view_products.py --stats
```

---

## Long-term Strategy

**Best approach**: Prioritize API-based data sources over HTML parsing:

1. **Leonteq API** ✓ - Most comprehensive
2. **AKB API** (if available) - Investigate
3. **Swissquote API** (if available) - Investigate
4. **HTML Parsers** - Use as fallback only

HTML parsers are fragile and break when websites change. APIs provide structured, reliable data.
