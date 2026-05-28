"""
Create or update Prefect deployments at container startup.

This is all idempotent. Calling it repeatedly will update existing
deployments or create them if missing.
"""

import asyncio
import os

from loguru import logger
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.deployments.runner import RunnerDeployment
from prefect.exceptions import ObjectAlreadyExists

_FLOW_BASE_DIR = os.environ.get(
    "PREFECT_FLOW_BASE_DIR",
    "/opt/packages/openalex_snapshot_processor/prefect_config/flows",
)
CONCURRENCY_LIMIT = int(os.environ.get("PREFECT_WORK_POOL_CONCURRENCY_LIMIT", 8))


async def _ensure_work_pool_exists(
    pool_name: str,
    pool_type: str = "process",
    concurrency_limit: int | None = CONCURRENCY_LIMIT,
) -> None:
    """
    Create the Prefect work pool if it doesn't already exist.

    Args:
        pool_name (str): The name of the work pool to create.
        pool_type (str): The type of the work pool, e.g. "process" or "thread". Defaults to "process".
        concurrency_limit (int | None): An optional concurrency limit for the work pool. Defaults to 8.

    """
    async with get_client() as client:
        try:
            await client.create_work_pool(
                WorkPoolCreate(
                    name=pool_name,
                    type=pool_type,
                    concurrency_limit=concurrency_limit,
                )
            )
            logger.info(f"Work pool '{pool_name}' created (type={pool_type})")
            logger.info(f"Concurrency limit set to {concurrency_limit}")
        except ObjectAlreadyExists:
            logger.info(f"Work pool '{pool_name}' already exists, skipping creation")
            await client.update_work_pool(
                work_pool_name=pool_name,
                work_pool=WorkPoolUpdate(concurrency_limit=concurrency_limit),
            )
            logger.info(
                f"Work pool '{pool_name}' updated with concurrency limit {concurrency_limit}"
            )


async def _create_deployment_on_load(
    entrypoint: str, name: str, pool: str, queue: str
) -> None:
    """
    Create or update a Prefect deployment for the given flow entrypoint.

    Runs at container startup to ensure that necessary deployments are registered with Prefect.

    Args:
        entrypoint (str): Absolute-path entrypoint of type `path/to/file.py:function`.
        name (str): Name of the deployment.
        pool (str): Name of the work pool to use for the deployment.
        queue (str): Name of the work queue to use for the deployment.

    """
    try:
        logger.info(f"Loading flow from {entrypoint}")
        deployment = RunnerDeployment.from_entrypoint(
            entrypoint=entrypoint,
            name=name,
            work_pool_name=pool,
            work_queue_name=queue,
        )

        logger.info(f"Applying deployment {name} (flow={deployment.flow_name})")
        deployment_id = await deployment.apply()
        logger.info(f"Deployment {name} applied (id={deployment_id})")

    except Exception as prefect_exception:  # noqa: BLE001 # just catching all prefect exceptions here to log them, not to handle them differently
        logger.exception(f"Failed to apply deployment {name}: {prefect_exception}")


async def main() -> None:
    """Register or update all flows as deployments on container startup."""
    work_pool = "local-pool"
    work_queue = "local-pool"

    await _ensure_work_pool_exists(work_pool)

    deployments = [
        (
            f"{_FLOW_BASE_DIR}/openalex_snapshot_flow.py:openalex_snapshot_ingest",
            "openalex-snapshot-ingest",
        ),
        (
            f"{_FLOW_BASE_DIR}/smoke_test_local.py:smoke_test_local",
            "smoke-test-local",
        ),
        (
            f"{_FLOW_BASE_DIR}/smoke_test_azure.py:smoke_test_azure",
            "smoke-test-azure",
        ),
    ]

    for entrypoint, name in deployments:
        await _create_deployment_on_load(entrypoint, name, work_pool, work_queue)


if __name__ == "__main__":
    asyncio.run(main())
