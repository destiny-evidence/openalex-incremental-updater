# OpenAlex Incremental Updater

A service to offer incremental updates from the OpenAlex API to the DESTINY repository.

## Overview

This repository contains two main components:

- **OpenAlex Incremental Updater**: A FastAPI service that fetches and processes updates from the OpenAlex API, storing them in a PostgreSQL database.
- **Refresh Requester**: A service that periodically requests updates from the OpenAlex Incremental Updater service, ensuring that the database is kept up-to-date with the latest changes.

OpenAlex Incremental Updater is intended to be run as an Azure Container App, scaled to zero replicas when not in use. It is designed to be triggered on a regular basis by the Refresh Requester service, which is run as an Azure Container App Job. The Refresh Requester service calls the OpenAlex Incremental Updater API to fetch updates, uploads them to internal Azure Blob Storage, generates share access signatures (SAS) for blobs and then trigger the DESTINY repository to process these updates.

Authentication against the DESTINY repository API is performed by an OpenAlex Incremental Updater endpoint using a registered Application in Azure. This endpoint is called by the Refresh Requester service to obtain an access token, which is then used to authenticate requests to the DESTINY repository API.

Diagrammatically, the architecture looks like this:

```mermaid
sequenceDiagram
    participant RR as Refresh Requester
    participant OIU as OpenAlex Incremental Updater
    participant OA as OpenAlex API
    participant ABS as Azure Blob Storage
    participant DR as DESTINY Repository API

    RR->>OIU: Calls API
    OIU->>OA: Requests updates
    OA->>OIU: Returns updates
    OIU->>RR: Processes updates
    RR->>ABS: Stores updates
    RR->>OIU: Requests bearer token
    OIU->>DR: Authenticates against API
    DR->>OIU: Returns bearer token
    OIU->>RR: Returns bearer token
    RR->>ABS: Generates SAS
    RR->>DR: Registers ingestion
    RR->>ABS: Uploaders metadata associated with ingest
```

## Developers

Dependency management is handled by [Poetry](https://python-poetry.org/). To install Poetry, follow the instructions on the [Poetry installation page](https://python-poetry.org/docs/#installation). Ensure you install poetry version 2.1.2 or later, as this is the version used in the Dockerfiles and Poetry will shout at you about lock file version mismatches if you use an earlier version.

See the documentation within the [openalex_incremental_updater](openalex_incremental_updater) and [refresh_requester](refresh_requester) packages for details on how to install and run the service.

Ensure you install the pre-commit hooks by running:

```bash
poetry run pre-commit install
```

after installing dependencies. This will ensure that code is automatically formatted and linted before committing changes.

### Running locally

To run the service locally, run the following commands from their respective directories:

```bash
    uvicorn openalex_incremental_updater.main:app --reload
```

```bash
    python refresh_requester/main.py
```

By default, `openalex-incremental-updater` will run on port 8000. Automatically generated API documentation will be available at `http://localhost:8000/docs`. You can change the port by modifying the command above with the `--port` flag.

### Containerisation

`Dockerfile`s are used to build container images for the service when deployed in Azure, and can also be used to run the service locally. Two convenience scripts are provided in the root of the repository to build and run both services in Docker containers.

To build the images, run:

```bash
./build_openalex_incremental_updater.sh
./build_refresh_requester.sh
```

Optional flags include:

- `--tag` to specify a custom tag for the image. The default tag is `latest`.
- `--no-cache` to build the image without using the cache, which can be useful if you want to ensure all dependencies are freshly installed.

Then run the built images with the convenience scripts:

```bash
./run_openalex_incremental_updater.sh
./run_refresh_requester.sh
```

Environment variables should be set in the respective `.env` files in the `openalex_incremental_updater` and `refresh_requester` directories. These files should not be committed to version control, as they may contain sensitive information such as API keys or database connection strings.

A `compose.yml` file is provided to run both services together in a Docker Compose environment. To start the services, run:

```bash
docker compose up --build
```

Which will successfully network the two services together, allowing the Refresh Requester to call the OpenAlex Incremental Updater API.

### Testing

To run the tests for the OpenAlex Incremental Updater and Refresh Requester services, use the following commands in their respective directories:

```bash
    poetry run pytest
```

## Deployment

The OpenAlex Incremental Updater is deployed as an Azure Container App, which is scaled to zero replicas when not in use. The Refresh Requester is deployed as an Azure Container App Job, which runs on a schedule to trigger the OpenAlex Incremental Updater service. This is currently set to run once per day at 04:00 UTC, refreshing data for the previous day.

The deployment is managed using GitHub Actions, which automatically builds and pushes the Docker images to the Azure Container Registry, and updates the Azure Container App with the latest image. Staging deployments are made automatically on successful pull request merges to the `main` branch, while production deployments are triggered manually via a GitHub Actions workflow, which promotes the latest staging deployment to production. Environment variables for the Azure Container App are set using GitHub Secrets, ensuring that sensitive information is not exposed in the repository. Separate secrets are used for staging and production deployments, managed by GitHub Environments, allowing for different configurations in each environment.

Images are tagged with the short SHA of the commit, and a unique tag is generated for production deployments by appending `-prod` to the short SHA. This allows for easy identification of the image version in use.
