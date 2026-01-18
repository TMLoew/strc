from __future__ import annotations

import time
from typing import Optional, Callable

import httpx

from core.models import NormalizedProduct, make_field, Underlying
from core.utils.text import truncate_excerpt

BASE_URL = "https://structuredproducts-ch.leonteq.com"
API_ENDPOINT = f"{BASE_URL}/rfb-api/products"


def _build_request_payload(offset: int, page_size: int, filters: dict | None = None) -> dict:
    """Build the POST request body for /rfb-api/products endpoint."""
    payload = {
        "region": "CH",
        "pagination": {
            "resultPerPage": page_size,
            "resultsOffset": offset
        },
        "sort": [
            {"fieldName": "underlying.shortName.keyword", "sortOrder": "ASC"},
            {"fieldName": "payoff.bearish", "sortOrder": "ASC"},
            {"fieldName": "calendar.finalFixingDate", "sortOrder": "ASC"},
            {"fieldName": "levels.strikeLevelAbs", "sortOrder": "DESC"},
            {"fieldName": "listings.markets.marketVenue", "sortOrder": "ASC"},
            {"fieldName": "price.metrics.delta", "sortOrder": "DESC"}
        ],
        "conditions": {
            "-identification.status:EXPIRED": True,
            "+_exists_:levels.stopLossLevelAbs": False,
            "+priceIndication.extendedTradingHours:true": False,
            "+calendar.issueDateTime:[* TO now]": True
        },
        "currencies": [],
        "underlyings": [],
        "productTypes": [],
        "omni": ""
    }

    if filters:
        payload.update(filters)

    return payload


def fetch_products_page(
    token: str,
    offset: int = 0,
    page_size: int = 50,
    filters: dict | None = None
) -> dict:
    """
    Fetch a single page from Leonteq /rfb-api/products endpoint.

    Args:
        token: JWT Bearer token for authentication
        offset: Pagination offset (resultsOffset)
        page_size: Results per page (resultPerPage, max 50)
        filters: Optional filter overrides for conditions/currencies/etc

    Returns:
        Raw API response dict with 'products' and 'searchMetadata'

    Raises:
        ValueError: If token is not provided
        RuntimeError: For various API errors (invalid token, forbidden, rate limited, timeout)
        httpx.HTTPStatusError: For other HTTP errors
    """
    if not token:
        raise ValueError("leonteq_api_token not configured")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = _build_request_payload(offset, page_size, filters)

    max_retries = 3
    retry_delay = 5.0  # seconds

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(API_ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RuntimeError("leonteq_api_token_invalid") from e
            elif e.response.status_code == 403:
                raise RuntimeError("leonteq_api_forbidden") from e
            elif e.response.status_code == 429:
                raise RuntimeError("leonteq_api_rate_limited") from e
            elif e.response.status_code >= 500 and attempt < max_retries - 1:
                # Retry on 500 errors
                print(f"Leonteq API: Server error {e.response.status_code}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            else:
                raise RuntimeError(f"leonteq_api_error_{e.response.status_code}") from e
        except (httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            if attempt < max_retries - 1:
                # Retry on timeout/disconnect errors
                error_type = type(e).__name__
                print(f"Leonteq API: {error_type}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            else:
                raise RuntimeError(f"leonteq_api_timeout") from e
        except httpx.ConnectError as e:
            raise RuntimeError("leonteq_api_connection_failed") from e


def get_product_type_counts(token: str) -> dict[str, int]:
    """
    Get count of products by product type from the API.

    This helps determine how to segment the crawl to avoid the 10K limit.

    Args:
        token: JWT Bearer token for authentication

    Returns:
        Dictionary mapping product type codes to product counts
    """
    # Fetch first page to get metadata about available facets
    response = fetch_products_page(token, offset=0, page_size=1)
    metadata = response.get("searchMetadata", {})

    # Extract product type facets if available
    facets = metadata.get("facets", {})
    product_type_facets = facets.get("productTypes", [])

    type_counts = {}
    for facet in product_type_facets:
        type_code = facet.get("code")
        count = facet.get("count", 0)
        if type_code:
            type_counts[type_code] = count

    return type_counts


def fetch_all_products(
    token: str,
    page_size: int = 50,
    max_products: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    product_callback: Callable[[dict], None] | None = None,
    checkpoint_callback: Callable[[int], None] | None = None,
    rate_limit_ms: int = 100,
    resume_from_offset: int = 0,
    filters: dict | None = None
) -> list[dict]:
    """
    Fetch ALL products by paginating through the API.

    Args:
        token: JWT Bearer token for authentication
        page_size: Results per page (default 50, max 50 per API spec)
        max_products: Optional limit for testing (None = fetch all)
        progress_callback: Optional callback(completed, total) for progress tracking
        product_callback: Optional callback(product_dict) called for each product immediately after fetch
        checkpoint_callback: Optional callback(offset) called periodically to save checkpoint
        rate_limit_ms: Delay between requests in milliseconds
        resume_from_offset: Offset to resume from (for crash recovery)

    Returns:
        List of all product dicts from API (only if product_callback is None)
    """
    products = []
    offset = resume_from_offset
    total_hits = None
    products_fetched = resume_from_offset

    while True:
        # Fetch page with filters
        response = fetch_products_page(token, offset, page_size, filters)
        page_products = response.get("products", [])
        metadata = response.get("searchMetadata", {})

        # First page: capture total
        if total_hits is None:
            total_hits = metadata.get("totalHits", 0)
            if resume_from_offset > 0:
                print(f"Leonteq API: Resuming from offset {resume_from_offset}/{total_hits} products...")
            else:
                print(f"Leonteq API: Starting fetch of {total_hits} products...")
            if progress_callback:
                progress_callback(products_fetched, total_hits)

        # Process each product
        for product in page_products:
            products_fetched += 1

            # Call product callback immediately if provided
            if product_callback:
                product_callback(product)
            else:
                # Otherwise accumulate in list
                products.append(product)

        # Progress update (show every 5 pages)
        if products_fetched % (page_size * 5) == 0 or products_fetched == total_hits:
            print(f"Leonteq API: Fetched {products_fetched}/{total_hits} products ({products_fetched/total_hits*100:.1f}%)")

        if progress_callback:
            progress_callback(products_fetched, total_hits)

        # Save checkpoint every 500 products
        if products_fetched % 500 == 0:
            print(f"DEBUG: Checkpoint trigger at {products_fetched}, callback exists: {checkpoint_callback is not None}")
            if checkpoint_callback:
                checkpoint_callback(offset + page_size)

        # Check termination conditions
        if not page_products:  # No more results
            break
        if max_products and products_fetched >= max_products:  # Testing limit
            if not product_callback:
                products = products[:max_products]
            break
        if products_fetched >= total_hits:  # Fetched all
            break

        # Next page
        offset += page_size

        # Rate limiting
        if rate_limit_ms > 0:
            time.sleep(rate_limit_ms / 1000.0)

    return products


def _fetch_segment_recursive(
    token: str,
    search_prefix: str,
    page_size: int,
    product_callback: Callable[[dict], None] | None,
    rate_limit_ms: int,
    depth: int = 0,
    user_filters: dict | None = None
) -> int:
    """
    Recursively fetch a segment, sub-dividing if it exceeds 10K limit.

    Args:
        token: JWT Bearer token
        search_prefix: Search string (e.g., "A", "AB", "ABC")
        page_size: Products per page
        product_callback: Callback for each product
        rate_limit_ms: Rate limit in ms
        depth: Recursion depth (for logging)
        user_filters: Optional user-specified filters to combine with search

    Returns:
        Number of products fetched
    """
    indent = "  " * depth

    # Build combined filters (search + user filters)
    combined_filters = {"omni": search_prefix}
    if user_filters:
        # Handle symbols - convert to omni search
        if user_filters.get("symbols"):
            # If user specified symbols, use them instead of alphabet search
            combined_filters["omni"] = " OR ".join(user_filters["symbols"])
        if user_filters.get("product_types"):
            combined_filters["productTypes"] = user_filters["product_types"]
        if user_filters.get("currencies"):
            combined_filters["currencies"] = user_filters["currencies"]

    # Check segment size
    response = fetch_products_page(token, offset=0, page_size=1, filters=combined_filters)
    segment_size = response.get("searchMetadata", {}).get("totalHits", 0)

    if segment_size == 0:
        return 0

    # If under 10K, fetch directly
    if segment_size < 10000:
        print(f"{indent}Fetching '{search_prefix}' ({segment_size:,} products)...")

        products = fetch_all_products(
            token=token,
            page_size=page_size,
            max_products=None,
            progress_callback=None,
            product_callback=product_callback,
            checkpoint_callback=None,
            rate_limit_ms=rate_limit_ms,
            filters=combined_filters
        )

        count = len(products) if not product_callback else segment_size
        print(f"{indent}✓ '{search_prefix}' complete: {count:,} products")
        return count

    # Segment too large - subdivide
    print(f"{indent}Segment '{search_prefix}' has {segment_size:,} products (>10K) - subdividing...")

    # Try subdividing with A-Z, then 0-9
    sub_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    total_fetched = 0

    for char in sub_chars:
        sub_prefix = search_prefix + char
        fetched = _fetch_segment_recursive(
            token=token,
            search_prefix=sub_prefix,
            page_size=page_size,
            product_callback=product_callback,
            rate_limit_ms=rate_limit_ms,
            depth=depth + 1,
            user_filters=user_filters
        )
        total_fetched += fetched

        if fetched > 0:
            time.sleep(rate_limit_ms / 1000.0)  # Rate limit between segments

    print(f"{indent}✓ '{search_prefix}' subdivision complete: {total_fetched:,} products total")
    return total_fetched


def fetch_all_products_segmented(
    token: str,
    page_size: int = 50,
    max_products: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    product_callback: Callable[[dict], None] | None = None,
    checkpoint_callback: Callable[[int], None] | None = None,
    rate_limit_ms: int = 100,
    user_filters: dict | None = None
) -> list[dict]:
    """
    Fetch ALL products using recursive segmented approach to bypass 10K API limit.

    This function segments the crawl by underlying name (alphabetically) and
    automatically subdivides any segment that exceeds 10,000 products.

    Example: If "A" has 15,000 products, it will fetch:
      - "AA", "AB", "AC", ... "AZ", "A0", "A1", ..., "A9"
      - If "AB" also exceeds 10K, it will subdivide further: "ABA", "ABB", etc.

    Args:
        token: JWT Bearer token for authentication
        page_size: Results per page (default 50, max 50 per API spec)
        max_products: Optional limit for testing (None = fetch all)
        progress_callback: Optional callback(completed, total) for progress tracking
        product_callback: Optional callback(product_dict) called for each product
        checkpoint_callback: Optional callback(offset) - NOT USED in segmented mode
        rate_limit_ms: Delay between requests in milliseconds
        user_filters: Optional user-specified filters (product_types, symbols, currencies)

    Returns:
        List of all product dicts from API (only if product_callback is None)
    """
    print("Leonteq API: Using recursive segmented crawl to bypass 10K limit...")

    # Build initial filter check (with user filters if provided)
    initial_filters = None
    if user_filters:
        initial_filters = {}
        if user_filters.get("product_types"):
            initial_filters["productTypes"] = user_filters["product_types"]
        if user_filters.get("currencies"):
            initial_filters["currencies"] = user_filters["currencies"]
        if user_filters.get("symbols"):
            initial_filters["omni"] = " OR ".join(user_filters["symbols"])

    # First, get total count (with user filters if provided)
    initial_response = fetch_products_page(token, offset=0, page_size=1, filters=initial_filters)
    total_products = initial_response.get("searchMetadata", {}).get("totalHits", 0)
    print(f"Leonteq API: Total products available: {total_products:,}")

    # If under 10K, use standard fetch
    if total_products < 10000:
        print(f"Leonteq API: Total under 10K limit, using standard fetch")
        return fetch_all_products(
            token=token,
            page_size=page_size,
            max_products=max_products,
            progress_callback=progress_callback,
            product_callback=product_callback,
            checkpoint_callback=checkpoint_callback,
            rate_limit_ms=rate_limit_ms,
            filters=initial_filters
        )

    # Use recursive segmentation starting with A-Z + 0-9
    # Unless user specified specific symbols (then use those instead)
    if user_filters and user_filters.get("symbols"):
        print(f"Leonteq API: Using symbol-based segmentation for: {user_filters['symbols']}")
        root_segments = user_filters["symbols"]
    else:
        print("Leonteq API: Starting recursive alphabet segmentation...")
        root_segments = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # Track progress
    products_fetched = 0
    all_products = []

    # Wrap product callback to track progress
    def tracked_callback(product: dict):
        nonlocal products_fetched
        products_fetched += 1

        if product_callback:
            product_callback(product)
        else:
            all_products.append(product)

        # Update progress periodically
        if progress_callback and products_fetched % 100 == 0:
            progress_callback(products_fetched, total_products)

    # Fetch each root segment recursively
    for segment in root_segments:
        if max_products and products_fetched >= max_products:
            print(f"Leonteq API: Reached max_products limit ({max_products})")
            break

        fetched = _fetch_segment_recursive(
            token=token,
            search_prefix=segment,
            page_size=page_size,
            product_callback=tracked_callback if product_callback or progress_callback else None,
            rate_limit_ms=rate_limit_ms,
            depth=0,
            user_filters=user_filters
        )

        if not (product_callback or progress_callback):
            products_fetched += fetched

    # Final progress update
    if progress_callback:
        progress_callback(products_fetched, total_products)

    print(f"\nLeonteq API: Recursive segmented crawl complete: {products_fetched:,}/{total_products:,} products")

    return all_products if not product_callback else []


def parse_api_product(api_product: dict) -> NormalizedProduct:
    """
    Map Leonteq API JSON structure to NormalizedProduct.
    
    Improved version with better field mappings based on actual API response structure.
    """
    product = NormalizedProduct()
    source = "leonteq_api"

    # ISIN (required field)
    identifiers = api_product.get("identifiers", {})
    isin = identifiers.get("isin")
    if not isin:
        raise ValueError(f"Product missing ISIN: {identifiers}")
    product.isin = make_field(isin, 0.9, source, truncate_excerpt(f"identifiers.isin: {isin}"))

    # Valor
    valor = identifiers.get("valor")
    if valor:
        product.valor_number = make_field(str(valor), 0.9, source, truncate_excerpt(f"identifiers.valor: {valor}"))

    # Symbol/Ticker
    symbol = identifiers.get("symbol")
    if symbol:
        product.ticker_six = make_field(symbol, 0.8, source)

    # WKN
    wkn = identifiers.get("wkn")
    if wkn:
        product.wkn = make_field(wkn, 0.8, source)

    # Underlying information - use shortName for product name
    underlying_data = api_product.get("underlying", {})
    if underlying_data.get("shortName"):
        product.product_name = make_field(underlying_data["shortName"], 0.8, source)

    # Product type
    product_type_data = api_product.get("productType", {})
    if product_type_data.get("name"):
        product.product_type = make_field(product_type_data["name"], 0.8, source)

    # SSPA Category
    sspa_category = product_type_data.get("sspaCategory")
    if sspa_category:
        product.sspa_category = make_field(sspa_category, 0.8, source)

    # Issuer
    issuer_data = api_product.get("issuer", {})
    if issuer_data.get("name"):
        product.issuer_name = make_field(issuer_data["name"], 0.9, source)

    # Issuer LEI
    lei = issuer_data.get("lei")
    if lei:
        product.issuer_lei = make_field(lei, 0.9, source)

    # Currency
    currency = api_product.get("currency")
    if currency:
        product.currency = make_field(currency, 0.9, source)

    # Denomination
    denomination = api_product.get("denomination")
    if denomination is not None:
        product.denomination = make_field(float(denomination), 0.9, source)

    # Dates - Calendar
    calendar = api_product.get("calendar", {})

    # Maturity date (finalFixingDate)
    maturity = calendar.get("finalFixingDate")
    if maturity:
        product.maturity_date = make_field(maturity, 0.9, source)

    # Issue date
    issue_date = calendar.get("issueDateTime")
    if issue_date:
        product.settlement_date = make_field(issue_date, 0.8, source)

    # Initial fixing date
    initial_fixing = calendar.get("initialFixingDate")
    if initial_fixing:
        product.initial_fixing_date = make_field(initial_fixing, 0.8, source)

    # Subscription dates
    subscription_start = calendar.get("subscriptionStartDate")
    if subscription_start:
        product.subscription_start_date = make_field(subscription_start, 0.8, source)

    subscription_end = calendar.get("subscriptionEndDate")
    if subscription_end:
        product.subscription_end_date = make_field(subscription_end, 0.8, source)

    # Listing venues
    listings = api_product.get("listings", {})
    markets = listings.get("markets", [])
    if markets and isinstance(markets, list):
        venues = [m.get("marketVenue") for m in markets if m.get("marketVenue")]
        if venues:
            product.listing_venue = make_field(", ".join(venues), 0.7, source)

    # Parse underlying components for detailed underlying information
    underlying_components = underlying_data.get("underlyingComponents", [])
    underlyings_list = []

    # Levels (strike, barrier, etc.) - these apply to the basket/product
    levels = api_product.get("levels", {})

    if underlying_components and isinstance(underlying_components, list):
        # Multi-underlying product (basket)
        for comp in underlying_components:
            underlying_obj = Underlying()

            # Underlying name
            name = comp.get("name")
            if name:
                underlying_obj.name = make_field(name, 0.9, source)

            # Underlying ISIN
            underlying_isin = comp.get("isin")
            if underlying_isin:
                underlying_obj.isin = make_field(underlying_isin, 0.9, source)

            # RIC code
            ric = comp.get("ricCode")
            if ric:
                underlying_obj.ric_code = make_field(ric, 0.8, source)

            # Bloomberg ticker
            bloomberg = comp.get("bloombergTicker")
            if bloomberg:
                underlying_obj.bloomberg_ticker = make_field(bloomberg, 0.8, source)

            # Currency
            underlying_currency = comp.get("currency")
            if underlying_currency:
                underlying_obj.reference_currency = make_field(underlying_currency, 0.8, source)

            # Weight (for basket products)
            weight = comp.get("weight")
            if weight is not None:
                underlying_obj.weight_pct = make_field(float(weight) * 100, 0.8, source)

            underlyings_list.append(underlying_obj)

    # If no underlyingComponents, create single underlying from top-level data
    if not underlyings_list:
        underlying_obj = Underlying()

        # Set underlying name from shortName
        if underlying_data.get("shortName"):
            underlying_obj.name = make_field(underlying_data["shortName"], 0.8, source)

        # Product-level strike
        strike = levels.get("strikeLevelAbs")
        if strike is not None:
            underlying_obj.strike_level = make_field(float(strike), 0.7, source)

        # Product-level barrier
        barrier = levels.get("barrierLevelAbs")
        if barrier is not None:
            underlying_obj.barrier_level = make_field(float(barrier), 0.7, source)

        # Knock-in level (common in barrier products)
        knock_in = levels.get("knockInLevelAbs")
        if knock_in is not None:
            if not underlying_obj.barrier_level:
                underlying_obj.barrier_level = make_field(float(knock_in), 0.7, source)

        # Add if it has meaningful data
        if underlying_obj.name or underlying_obj.strike_level or underlying_obj.barrier_level:
            underlyings_list.append(underlying_obj)

    # Also add product-level strike/barrier to all underlyings if they don't have individual levels
    if underlyings_list:
        product_strike = levels.get("strikeLevelAbs")
        product_barrier = levels.get("barrierLevelAbs")
        product_knock_in = levels.get("knockInLevelAbs")

        for underlying_obj in underlyings_list:
            if not underlying_obj.strike_level and product_strike is not None:
                underlying_obj.strike_level = make_field(float(product_strike), 0.6, source)

            if not underlying_obj.barrier_level:
                if product_barrier is not None:
                    underlying_obj.barrier_level = make_field(float(product_barrier), 0.6, source)
                elif product_knock_in is not None:
                    underlying_obj.barrier_level = make_field(float(product_knock_in), 0.6, source)

        product.underlyings = underlyings_list

    # Coupon information
    coupon_data = api_product.get("coupon", {})
    coupon_rate = coupon_data.get("rate")
    if coupon_rate is not None:
        product.coupon_rate_pct_pa = make_field(float(coupon_rate), 0.8, source)

    coupon_frequency = coupon_data.get("frequency")
    if coupon_frequency:
        product.coupon_frequency = make_field(coupon_frequency, 0.8, source)

    coupon_type = coupon_data.get("type")
    if coupon_type:
        product.coupon_type = make_field(coupon_type, 0.7, source)

    # Settlement type and currency
    settlement_data = api_product.get("settlement", {})
    settlement_type = settlement_data.get("type")
    if settlement_type:
        product.settlement_type = make_field(settlement_type, 0.7, source)

    settlement_currency = settlement_data.get("currency")
    if settlement_currency:
        product.settlement_currency = make_field(settlement_currency, 0.8, source)

    # Participation rate (common in structured products)
    payoff_data = api_product.get("payoff", {})
    participation = payoff_data.get("participationRate")
    if participation is not None:
        product.participation_rate_pct = make_field(float(participation) * 100, 0.7, source)

    return product
