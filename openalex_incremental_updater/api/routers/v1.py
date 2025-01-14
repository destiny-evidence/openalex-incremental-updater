"""API Router definitions for the OpenAlex Incremental Updater - version 1."""

from fastapi import APIRouter

from openalex_incremental_updater.api.core.config import get_settings
from openalex_incremental_updater.api.routers import utils

settings = get_settings()

router = APIRouter(prefix=settings.API_V1_STR, tags=["v1"])
router.include_router(utils.router)
