from pathlib import Path

from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    data_dir: Path = BASE_DIR / "data"
    db_path: Path = BASE_DIR / "data" / "structured_products.db"
    input_dir: Path = BASE_DIR / "input"
    not_reviewed_dir: Path = BASE_DIR / "not_reviewed_yet"
    reviewed_dir: Path = BASE_DIR / "reviewed"
    to_be_signed_dir: Path = BASE_DIR / "to_be_signed"
    output_dir: Path = BASE_DIR / "output"

    leonteq_username: str | None = None
    leonteq_password: str | None = None
    leonteq_otp_secret: str | None = None
    swissquote_username: str | None = None
    swissquote_password: str | None = None
    enable_crawl: bool = True
    crawl_interval_hours: int = 24
    enable_portal_crawl: bool = True
    enable_swissquote_scanner_crawl: bool = True
    crawl_max_workers: int = 10
    enable_yahoo_enrich: bool = False
    enable_akb_enrichment: bool = False  # Disable enrichment by default (makes AKB crawl much faster)

    # Leonteq API crawler settings
    leonteq_api_token: str | None = None
    enable_leonteq_api_crawl: bool = True
    leonteq_api_page_size: int = 50
    leonteq_api_max_products: int | None = None
    leonteq_api_rate_limit_ms: int = 100
    leonteq_api_exclude_expired: bool = True

    class Config:
        env_prefix = "SPA_"
        env_file = ".env"


settings = Settings()
