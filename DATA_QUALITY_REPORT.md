# Data Quality Report

## Current Database Statistics

**Total Products**: 18,525

### By Source

| Source | Count | % of Total |
|--------|-------|------------|
| AKB Finanzportal | 8,319 | 44.9% |
| Leonteq API | 5,141 | 27.7% |
| Swissquote HTML | 4,183 | 22.6% |
| Leonteq HTML | 882 | 4.8% |

## Data Quality by Source

### Field Coverage Analysis

| Source | Coupon | Underlyings | Barrier | Notes |
|--------|--------|-------------|---------|-------|
| **AKB Finanzportal** | 647 (7.8%) | 1,984 (23.8%) | 698 (8.4%) | ✅ Best for coupon/barrier data |
| **Leonteq API** | 0 (0%) | 5,141 (100%) | 0 (0%) | ✅ Excellent for underlyings |
| **Swissquote HTML** | 0 (0%) | 0 (0%) | 0 (0%) | ❌ Needs parser enhancement |
| **Leonteq HTML** | 0 (0%) | 0 (0%) | 0 (0%) | ❌ Needs parser enhancement |

### Why Low Coverage?

#### 1. Not All Products Have These Features

Many structured products simply don't have coupons, barriers, or multiple underlyings:

**Product Types Without Coupons**:
- Mini-Future (2,465 products) - Leveraged tracking products
- Warrant mit Knock-out (1,780 products) - Pure options
- Tracker-Zertifikat (783 products) - Index trackers
- Warrant (529 products) - Call/put options
- Constant Leverage Certificate (507 products) - Leveraged trackers

These represent ~6,064 products (33% of total) that legitimately don't have coupons.

**Products With Coupons**:
- Barrier Reverse Convertible (1,332 products) - Should have coupons
- Express-Zertifikat (119 products) - Should have coupons
- Reverse Convertible (153 products) - Should have coupons
- Credit Linked Notes (57 products) - Should have coupons

These represent ~1,661 products that SHOULD have coupon data.

**Current Coupon Coverage for Products That Should Have Them**:
- AKB has 647 coupons
- Expected ~1,661 products should have coupons
- **Coverage**: 39% (647/1,661)

#### 2. Parser Limitations

**Leonteq API**:
- ✅ Excellent underlying extraction (100%)
- ❌ Coupon data not returned by API OR not in expected format
- ❌ Barrier data not returned OR in different location

**Swissquote HTML**:
- ❌ Parser needs to be written/enhanced
- HTML contains data but not extracted

**Leonteq HTML**:
- ❌ Parser needs enhancement
- HTML contains data but not fully extracted

## Detailed Analysis

### AKB Finanzportal (Best Overall)

**Strengths**:
- Only source with meaningful coupon extraction (647 products)
- Good underlying coverage (1,984 products, 23.8%)
- Barrier detection working (698 products)
- Enhanced parser operational since reprocessing

**Example Products**:
```
CH0522935433: 5.1% p.a. coupon, 2 underlyings (Nestle, Roche), barrier
CH1446506862: 10.0% p.a. coupon, barrier
CH1446506904: 7.0% p.a. coupon, barrier
```

**Limitations**:
- Slow crawler (~1.8 products/sec due to API rate limits)
- Not all products have full termsheet data available
- Only 7.8% coupon coverage (but many products don't have coupons)

### Leonteq API (Best for Underlyings)

**Strengths**:
- ✅ **100% underlying coverage** (all 5,141 products have underlyings)
- Fast API access with filtering
- Rich metadata (ISIN, Valor, dates, venues)
- Recursive segmentation handles unlimited catalog size

**Example Products**:
```
CH1492307892: ABB underlying, strike 65.0, maturity 2026-02-20
CH1511797859: Underlying data complete
CH1511776549: Underlying data complete
```

**Limitations**:
- ❌ **0% coupon coverage** - API doesn't return coupon data
- ❌ **0% barrier coverage** - Barrier data not extracted
- No product type classification in many cases

**Why No Coupons?**
The Leonteq API parser looks for coupon data at `api_product.get("coupon", {}).get("rate")` but this field is apparently not populated in the API response. This could be because:
1. Leonteq API doesn't expose coupon data publicly
2. Coupon data requires authentication/different endpoint
3. Data is in a different field we haven't discovered

### Swissquote HTML (Needs Work)

**Current State**: Parser not extracting structured data

**Potential**:
- Large catalog (4,183 products)
- HTML likely contains termsheet data
- Could provide alternative source for coupons/barriers

**Action Needed**: Enhance parser to extract:
- Coupon rates
- Underlyings
- Barrier levels
- Product features

### Leonteq HTML (Needs Work)

**Current State**: Basic parser only

**Potential**:
- 882 products
- Authenticated HTML may have richer data than API
- Could complement Leonteq API data

**Action Needed**: Enhance parser similar to Swissquote

## Recommendations

### For Users

1. **Finding Products with Coupons**:
   - Filter by Source: "AKB Finanzportal"
   - Filter by Product Type: "Barrier Reverse Convertible" or "Express-Zertifikat"
   - Check "Coupon" field in product details

2. **Finding Products with Underlyings**:
   - Filter by Source: "Leonteq API" (100% coverage)
   - Or "AKB Finanzportal" (23.8% coverage)

3. **Understanding Missing Data**:
   - Check Source - different sources have different data quality
   - Some product types don't have coupons/barriers by design
   - Use Statistics page to see data coverage metrics

### For Developers

#### High Priority Improvements

1. **Investigate Leonteq API Coupon Data** (HIGH IMPACT)
   - Inspect actual API responses for coupon field
   - Check if authentication provides more data
   - May need to look at different API endpoints
   - **Potential Impact**: +5,141 products with coupon data (if available)

2. **Enhance Swissquote Parser** (HIGH IMPACT)
   - Extract coupon rates from HTML
   - Extract underlyings
   - Extract barrier levels
   - **Potential Impact**: +4,183 products with structured data

3. **Cross-Source Enrichment** (MEDIUM IMPACT)
   - When same ISIN exists in multiple sources, merge data
   - Example: Use Leonteq API for underlyings, AKB for coupons
   - **Potential Impact**: Better data completeness per product

#### Medium Priority Improvements

4. **Enhance Leonteq HTML Parser**
   - Extract additional fields not in API
   - **Potential Impact**: +882 products

5. **Add Data Quality Indicators**
   - Show data completeness score per product
   - Highlight which fields are missing
   - Indicate source reliability

#### Investigation Tasks

6. **Audit AKB Missing Coupons**
   - Query: Products with type "Reverse Convertible" but no coupon
   - Determine if parser needs enhancement or data truly missing
   - Check if specific product types need special handling

7. **Analyze Leonteq API Response Structure**
   - Capture sample API responses for products that should have coupons
   - Verify field names and structure
   - Update parser if coupon data is available

## Current State Summary

### What's Working Well ✅
- AKB parser extracting coupons, underlyings, barriers for subset of products
- Leonteq API providing 100% underlying coverage
- Database filtering by source/type working correctly
- Statistics page showing data quality metrics

### What Needs Improvement ❌
- Leonteq API not providing coupon data (0% coverage)
- Swissquote not extracting structured data (0% coverage)
- Leonteq HTML not extracting structured data (0% coverage)
- Overall coupon coverage: only 647/18,525 products (3.5%)

### Expected vs. Actual Coverage

**Products That Should Have Coupons** (~1,661):
- Barrier Reverse Convertible: 1,332
- Reverse Convertible: 153
- Express-Zertifikat: 119
- Credit Linked Notes: 57

**Actual Coupon Coverage**: 647 (39% of products that should have them)

**Products That Should Have Underlyings** (~12,000):
- Most structured products should have at least one underlying

**Actual Underlying Coverage**: 7,125 (59% of products that should have them)

## Action Plan

### Immediate (This Week)
1. ✅ Add source and product type filters (DONE)
2. ✅ Add statistics page showing data quality (DONE)
3. ✅ Document current data quality state (THIS DOCUMENT)

### Short Term (Next 2 Weeks)
1. ⏳ Investigate Leonteq API coupon field structure
2. ⏳ Enhance Swissquote HTML parser
3. ⏳ Add data quality indicators to product cards

### Medium Term (Next Month)
1. ⏳ Implement cross-source data enrichment
2. ⏳ Enhance Leonteq HTML parser
3. ⏳ Add data completeness scoring

### Long Term (Next Quarter)
1. ⏳ Automated data quality monitoring
2. ⏳ Parser testing framework
3. ⏳ Data validation rules

## Using the Application with Current Data

### Best Practices

1. **For Coupon-Based Strategies**:
   ```
   Source: AKB Finanzportal
   Product Type: Barrier Reverse Convertible
   → 1,332 products, ~50% have coupon data
   ```

2. **For Underlying Analysis**:
   ```
   Source: Leonteq API
   → 5,141 products, 100% have underlyings
   ```

3. **For Complete Termsheet Data**:
   ```
   Source: AKB Finanzportal
   Product Type: Express-Zertifikat or Barrier Reverse Convertible
   → Best chance of complete data
   ```

4. **For Large Product Universe**:
   ```
   Source: All
   → 18,525 products total
   → Accept that some fields will be missing
   → Use filters to focus on data-rich subsets
   ```

## Monitoring Data Quality

### Using Statistics Page

Navigate to **Statistics** tab to see:
- Total products by source
- Data quality percentages
- Recent crawl activity
- Maturity distribution

### Using SQL Queries

```sql
-- Check coupon coverage by product type
SELECT
    product_type,
    COUNT(*) as total,
    SUM(CASE WHEN json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL THEN 1 ELSE 0 END) as has_coupon,
    ROUND(100.0 * SUM(CASE WHEN json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as coverage_pct
FROM products
WHERE product_type LIKE '%Reverse Convertible%'
   OR product_type LIKE '%Express%'
GROUP BY product_type
ORDER BY total DESC;
```

This report will be updated as parsers are enhanced and data quality improves.

**Last Updated**: 2026-01-18
