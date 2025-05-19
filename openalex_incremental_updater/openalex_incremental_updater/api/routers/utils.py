"""Useful utility endpoints for the API."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["utils"])


@router.get("/health-check/")
async def health_check() -> JSONResponse:
    """
    Health check endpoint for the API.

    Returns:
        JSONResponse: Response indicating the API is healthy.

    """
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)
