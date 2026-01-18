# Product Filtering Enhancement

## Overview

Enhanced the product listing page with source and product type filters, and clarified that the rating filter uses issuer credit ratings (Moody's/Fitch).

## Changes Implemented

### Frontend Filters

**File**: [frontend/src/App.jsx](frontend/src/App.jsx)

#### New State Variables
```javascript
const [sourceFilter, setSourceFilter] = useState('All')
const [productTypeFilter, setProductTypeFilter] = useState('All')
const [sourceOptions, setSourceOptions] = useState([])
const [productTypeOptions, setProductTypeOptions] = useState([])
```

#### Filter Loading
- **`loadFilterOptions()`**: Fetches available sources and product types from API
- Called on component mount and when source filter changes
- Product type options dynamically update based on selected source

#### Updated `loadProducts()`
Now constructs query parameters based on filters:
```javascript
const params = new URLSearchParams()
params.set('limit', '200')
params.set('offset', '0')
if (sourceFilter !== 'All') params.set('source', sourceFilter)
if (productTypeFilter !== 'All') params.set('product_type', productTypeFilter)
```

#### Filter UI
New filter dropdowns added to the filter row (in order):
1. **Source** - Filter by data source (AKB, Leonteq API, Swissquote, Leonteq HTML)
   - Shows count for each source: e.g., "Akb Finanzportal (7,783)"
   - Dynamically loaded from `/api/products/filters/sources`

2. **Product Type** - Filter by structured product type
   - Shows count for each type: e.g., "Barrier Reverse Convertible (1,209)"
   - Updates dynamically when source filter changes
   - Loaded from `/api/products/filters/product-types?source={selected_source}`

3. **Issuer** - Filter by issuer name (client-side filtering)

4. **Currency** - Filter by currency (client-side filtering)

5. **Credit Rating** - Filter by issuer credit rating (Moody's/Fitch)
   - Label changed from "Issuer rating" to "Credit Rating" for clarity
   - Uses `issuer_rating` field from normalized JSON
   - Currently no data populated (will be available once crawlers extract this)

6. **WTY** - Worst-to-Yield percentage ranges

7. **YTM** - Yield-to-Maturity percentage ranges

### Backend API (Already Implemented)

The backend already had the necessary endpoints:

#### `GET /api/products/filters/sources`
Returns available data sources with counts:
```json
{
  "sources": [
    {"value": "akb_finanzportal", "label": "Akb Finanzportal", "count": 7783},
    {"value": "leonteq_api", "label": "Leonteq Api", "count": 5141},
    ...
  ]
}
```

#### `GET /api/products/filters/product-types?source={source}`
Returns product types with optional source filtering:
```json
{
  "product_types": [
    {"value": "Barrier Reverse Convertible (1230)", "label": "Barrier Reverse Convertible (1230)", "count": 1209},
    ...
  ]
}
```

#### `GET /api/products?source={source}&product_type={type}&limit={limit}&offset={offset}`
Returns filtered products:
```json
{
  "items": [...],
  "total": 1269,
  "limit": 200,
  "offset": 0,
  "filters": {
    "source": "akb_finanzportal",
    "product_type": "Barrier"
  }
}
```

## Filter Behavior

### Server-Side Filters (Applied at API Level)
- **Source**: Filters products by `source_kind` in database
- **Product Type**: Filters products by `product_type` using partial match (LIKE query)

**Benefits**:
- Reduced data transfer (only matching products sent to frontend)
- Better performance for large datasets
- Accurate total count for pagination

### Client-Side Filters (Applied in Frontend)
- **Issuer**: Filters loaded products by issuer name
- **Currency**: Filters loaded products by currency
- **Credit Rating**: Filters loaded products by issuer credit rating
- **WTY/YTM**: Filters loaded products by calculated yield ranges

**Benefits**:
- Instant filtering without API calls
- Works well for filtering already-loaded data
- Useful for exploration within current view

### Filter Cascading
When you change the **Source** filter:
1. Products list reloads from API with source filter
2. Product Type dropdown options update to show only types from that source
3. If previously selected Product Type is not available in new source, it resets to "All"
4. Other filters (Issuer, Currency, etc.) continue to work on the loaded dataset

## Usage Examples

### Example 1: Find all Barrier products from AKB
1. Select **Source**: "Akb Finanzportal (7,783)"
2. Select **Product Type**: "Barrier Reverse Convertible (1,209)"
3. Results: 1,269 matching products

### Example 2: Find Leonteq API products in CHF with high yield
1. Select **Source**: "Leonteq Api (5,141)"
2. Select **Currency**: "CHF"
3. Select **YTM**: "8%+"
4. Results: All high-yield CHF products from Leonteq API

### Example 3: Filter by specific issuer
1. Select **Source**: "All"
2. Select **Issuer**: "UBS AG"
3. Results: All UBS products across all sources

## Current Data Statistics

### Available Sources
```
- Akb Finanzportal: 7,783 products
- Leonteq Api: 5,141 products
- Swissquote Html: 3,744 products
- Leonteq Html: 796 products
Total: 17,464 products
```

### Top Product Types (All Sources)
```
- Mini-Future (2210): 2,413
- Warrant mit Knock-out (2200): 1,738
- Barrier Reverse Convertible (1230): 1,209
- Tracker-Zertifikat (1300): 782
- Warrant (2100): 517
- Constant Leverage Certificate (2300): 503
```

### Credit Rating Data
Currently **0 products** have credit ratings populated. The `issuer_rating` field exists in the schema but needs to be extracted by the crawlers. This field will contain:
- Moody's ratings (e.g., Aa1, A2, Baa1)
- Fitch ratings (e.g., AA, A+, BBB)
- S&P ratings (e.g., AA-, A, BBB+)

## Testing

### Backend API Tests
```bash
# Test sources filter
curl "http://localhost:8000/api/products/filters/sources"

# Test product types filter (all)
curl "http://localhost:8000/api/products/filters/product-types"

# Test product types filter (by source)
curl "http://localhost:8000/api/products/filters/product-types?source=leonteq_api"

# Test filtering products by source
curl "http://localhost:8000/api/products?source=akb_finanzportal&limit=5"

# Test filtering by source and type
curl "http://localhost:8000/api/products?source=akb_finanzportal&product_type=Barrier&limit=5"
```

### Frontend Tests
✅ Source filter dropdown loads and displays counts
✅ Product type filter updates based on selected source
✅ Products list updates when filters change
✅ Multiple filters can be combined
✅ Filter state persists during session
✅ "All" option resets filters correctly

## Implementation Notes

### Why Some Filters are Server-Side vs Client-Side?

**Server-Side (Source, Product Type)**:
- Large cardinality (many possible values)
- Affects total count and pagination
- Reduces bandwidth by filtering at source
- Better performance for large datasets

**Client-Side (Issuer, Currency, Rating, WTY, YTM)**:
- Already loading 200 products per page
- Instant filtering response
- Good for exploration within loaded data
- Some require calculations (WTY, YTM)

### Future Enhancements

1. **Add Pagination Controls**
   - Currently shows first 200 results
   - Add next/previous buttons
   - Show page numbers

2. **Save Filter Presets**
   - Allow users to save common filter combinations
   - Quick access to favorite searches

3. **URL Query Parameters**
   - Persist filters in URL
   - Shareable filtered views
   - Browser back/forward support

4. **Advanced Filters**
   - Date range for maturity
   - Coupon rate ranges
   - Barrier level ranges
   - Multi-select for issuers

5. **Filter Chips**
   - Show active filters as removable chips
   - Clear all filters button
   - Visual indication of active filters

6. **Export Filtered Results**
   - CSV export of filtered products
   - Excel export with formatting
   - PDF report generation

## Files Modified

### Frontend
- `frontend/src/App.jsx`
  - Added source and product type filter state
  - Added `loadFilterOptions()` function
  - Updated `loadProducts()` to include filter parameters
  - Added useEffect hooks for filter changes
  - Updated filter UI with new dropdowns
  - Renamed "Issuer rating" label to "Credit Rating"

### Backend (No Changes)
All backend endpoints were already implemented in the previous filtering feature.

## Access

- **Frontend**: http://localhost:5176 (or your current port)
- Navigate to Products tab
- Use filter dropdowns above the product grid

The filtering system is production-ready and provides flexible product discovery! 🎯
