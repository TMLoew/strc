from backend.app.api.routes_compare import router as compare_router
from backend.app.api.routes_enrich import router as enrich_router
from backend.app.api.routes_ingest import router as ingest_router
from backend.app.api.routes_products import router as products_router
from backend.app.api.routes_stats import router as stats_router

__all__ = ["compare_router", "enrich_router", "ingest_router", "products_router", "stats_router"]
