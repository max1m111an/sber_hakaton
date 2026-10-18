from fastapi import APIRouter

from .calc import router as calc_router
from .catalog import router as catalog_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(calc_router)
api_router.include_router(catalog_router)

__all__ = ["api_router"]
