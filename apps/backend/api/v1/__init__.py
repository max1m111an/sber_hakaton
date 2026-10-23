from fastapi import APIRouter

from .calc import router as calc_router
from .catalog import router as catalog_router
from .match import router as match_router

# /api/v1/... — калькуляторы и матчинг; /api/catalog/..., /api/regions — каталог в формате ТЗ
api_router = APIRouter()
api_router.include_router(calc_router)
api_router.include_router(match_router)
api_router.include_router(catalog_router)

__all__ = ["api_router"]
