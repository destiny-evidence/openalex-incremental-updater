# Refresh Requester

An app to repeatedly request the openalex incremental updater API provide a response, convert it from JSON to JSON-lines and upload it to blob storage.

## Overview

This service is designed to repeatedly request updates from the OpenAlex Incremental Updater API, convert the response from JSON to JSON-lines format, and upload the resulting data to Azure Blob Storage. It also handles authentication with the DESTINY Repository API and manages the registration of ingestion events.

## Architecture

The architecture of the Refresh Requester service is designed to interact with the OpenAlex Incremental Updater API and the DESTINY Repository API. The service performs the following steps:

1. **Fetch Updates**: The service calls the OpenAlex Incremental Updater API to fetch updates.
2. **Convert to JSON-lines**: The service converts the JSON response from the OpenAlex Incremental Updater API to JSON-lines format.
3. **Upload to Azure Blob Storage**: The service uploads the JSON-lines data to Azure Blob Storage.
4. **Authenticate with DESTINY Repository API**: The service calls the OpenAlex Incremental Updater API to obtain a bearer token for authentication against the DESTINY Repository API.
5. **Generate SAS**: The service generates a Shared Access Signature (SAS) for the uploaded blobs to allow the DESTINY repository secure access.
6. **Register Ingestion**: The service registers the ingestion event with the DESTINY Repository API, providing the necessary metadata and the SAS for the uploaded blobs.
7. **Upload Metadata**: The service uploads metadata associated with the ingestion to the DESTINY Repository API.

## Developers

Install the package with development and testing dependencies with:

```bash
uv sync --all-extras
```

This will allow you to use development- and test-time dependencies, as well as the main package dependencies.

### Environment Variables

Ensure you have a `.env` file in this directory with the following environment variables populated:

- `API_ENDPOINT`: The `openalex_works_ingest_date_range` endpoint of the OpenAlex Incremental Updater API that will provide incremental updates.
- `TOKEN_ENDPOINT`: The `auth_token` endpoint of the OpenAlex Incremental Updater API that will provide a bearer token for authentication against the DESTINY Repository API.
- `STORAGE_BLOB_ACCOUNT`: The name of the Azure Blob Storage account where the updates will be uploaded.
- `STORAGE_BLOB_CONTAINER`: The name of the Azure Blob Storage container where the updates will be uploaded.
- `STORAGE_BLOB_ACCOUNT_KEY`: The access key for the Azure Blob Storage account. You may need to generate this in Azure if you don't have it already.
- `REPOSITORY_ENDPOINT`: The endpoint of the DESTINY Repository API that will be used to register the ingestion and upload metadata. This will differ between `dev`, `staging`, and `prod` environments, and must be obtained from the [destiny-repository](http://github.com/destiny-evidence/destiny-repository) team, or can be found directly through the Azure Portal if you have access.

## Running locally

To run the service locally, run the following command from this directory:

```bash
python main.py
```

You will need to have an accessible OpenAlex Incremental Updater API endpoint and a DESTINY Repository API endpoint to test against. Ensure your `.env` file is correctly configured with the necessary environment variables.

## Containerisation

A `Dockerfile` is provided to build a container image for the service. To build the image, run the convenience script provided in the root of the repository:

```bash
./build_refresh_requester.sh
```

The image can then be run within a container with:

```bash
docker --env-file .env refresh-requester
```

or, alternatively, use the convenience script provided in the root of the repository:

```bash
./run_refresh_requester.sh
```

## Testing

Tests are provided in the `tests` directory and use the [pytest](https://pypi.org/project/pytest/) library. To run the tests, ensure you have the `uv` package installed, and run:

```bash
uv run pytest --cov=refresh_requester
```

from this directory.

## Azure Deployment

- Create an Azure Container App Job within the same container app environment as the OpenAlex Incremental Updater API. This will allow the job to run on a schedule and repeatedly request updates from the API.
- Set secrets in the Azure Container App Job to match those in the `.env` file. This is important for security, as the service should not expose sensitive information in the codebase. The recommended workflow is to add secrets to an Azure Key Vault, and then reference those secrets in the Azure Container App Job environment variables.
- Ensure the Azure Container App Job can only be accessed from within the Azure Container App Environment. This is important for security, as the service should not be publicly accessible.
- The Azure Container App Job should be configured to run on a schedule, once per day, to ensure it repeatedly requests updates from the OpenAlex Incremental Updater API.
- Push a built image to the Azure Container Registry, and then reference that image in the Azure Container App Job configuration.
- Ensure the Azure Container App Job has access to the Azure Blob Storage account and container where the updates will be uploaded. You will need to use a managed identity or service principal with the necessary permissions to access the Azure Blob Storage account and container, and provide necessary RBAC roles to the managed identity or service principal.
- Set environment variables in the Azure Container App Job to match those in the `.env` file, and reference the App Job Secrets you set previously rather than setting them manually. This ensures that there is a single place to change the environment variables.

Missing environment variables will cause the container to crash on startup. The recommended workflow is to add secrets to an Azure Key Vault, and then reference those secrets in the Azure Container App Job environment variables. You will need to ensure that the Azure Container App Job has access to the Azure Key Vault, and that the secrets are correctly referenced in the environment variables. Alternatively, they can be set as secrets directly in the Azure Container App Job configuration.
