"""Main module for the FastAPI application."""

from fastapi import APIRouter

from openalex_incremental_updater.api.routes import utils

api_router = APIRouter()
api_router.include_router(utils.router)
