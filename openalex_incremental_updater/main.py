"""OpenAlex Incremental Updater main module."""

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from openalex_incremental_updater.api.main import api_router
from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.logger import setup_logging


def custom_generate_unique_id(route: APIRoute) -> str:
    """
    Generate a unique ID for the route based on the tags and name.

    Args:
        route (APIRoute): The route to generate a unique ID for.

    Returns:
        str: Unique ID for the route

    """
    return f"{route.tags[0]}-{route.name}"


setup_logging(log_file="app_logs.log", log_level="DEBUG")

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=settings.allow_methods,
    allow_headers=settings.allow_headers,
)

app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=3000, reload=True)
