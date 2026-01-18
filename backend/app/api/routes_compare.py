from fastapi import APIRouter, Query

from backend.app.services import compare_products

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("")
def compare(ids: list[str] = Query(default_factory=list)) -> dict:
    return compare_products(ids)
