import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import compare_router, enrich_router, ingest_router, products_router, stats_router
from backend.app.db.session import init_db
from backend.app.services.akb_portal_service import crawl_akb_portal_catalog
from backend.app.services.akb_service import crawl_akb_enrich
from backend.app.services.swissquote_scanner_service import crawl_swissquote_scanner
from backend.app.settings import settings

app = FastAPI(title="Structured Products Analysis")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(compare_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(enrich_router, prefix="/api")

# Mount static files for status dashboard
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if settings.enable_crawl:
        asyncio.create_task(_daily_crawl())


async def _daily_crawl() -> None:
    while True:
        try:
            if settings.enable_portal_crawl:
                await asyncio.to_thread(crawl_akb_portal_catalog)
            if settings.enable_swissquote_scanner_crawl:
                await asyncio.to_thread(crawl_swissquote_scanner)
            await asyncio.to_thread(crawl_akb_enrich)
        except Exception:
            pass
        await asyncio.sleep(settings.crawl_interval_hours * 3600)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
