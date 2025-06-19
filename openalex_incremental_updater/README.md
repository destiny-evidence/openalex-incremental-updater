# OpenAlex Incremental Updater

A service to offer incremental updates from the OpenAlex API.

## Developers

Install the package with development and testing dependencies with:

```bash
poetry install --all-groups
```

This will allow you to use development- and test-time dependencies, as well as the main package dependencies.

In this early stage, remember to bump the version when you make changes to the code. See the [poetry versioning docs](https://python-poetry.org/docs/cli#version) to see how this is done for `MINOR`, `MAJOR`, `PATCH` (etc) changes _before_ you push your changes, or at least before they're merged into the main branch!

To run the application via either method detailed below, ensure you have a `.env` file in the root of the repository with the following environment variables populated:

- `CORS_ORIGINS`
- `USER_EMAIL`
- `OPENALEX_API_KEY`

(see `.env.example` for an example of how to format this file).

### Running locally

To run the service locally, run the following command from the root of the repository:

```bash
uvicorn openalex_incremental_updater.main:app --reload
```

By default, this will run on port 8000. Automatically generated API documentation will be available at `http://localhost:8000/docs`. You can change the port by modifying the command above with the `--port` flag.

### Containerisation

A `Dockerfile` is provided to build a container image for the service. To build the image, run:

```bash
docker build -t openalex-incremental-updater .
```

in the root of the repository.

Then run the built image within a container with:

```bash
docker run -p 8000:8000 --name openalex-app --env-file .env openalex-incremental-updater
```

referring to the `.env` file in the root of the repository mentioned above.

This is currently set up to run the service on port 8000, but this can be changed by modifying the `Dockerfile` and the `docker run` command. This may also be handled in future by container orchestration, along with secrets management.

### Testing

Tests are provided in the `tests` directory and use the [pytest](https://pypi.org/project/pytest/) library. To run the tests, ensure you have the `poetry` package installed, and run:

```bash
poetry run pytest
```

## Azure Deployment

- Create an Application Registration in your Azure Tenant as documented in the [Azure Samples documentation](https://github.com/Azure-Samples/ms-identity-python-daemon/tree/master/1-Call-MsGraph-WithSecret). Note down the Application (client) ID and Directory (tenant) ID
- Create a client secret for the application and note it down.
- Contact the [destiny-repository](https://github.com/destiny-evidence/destiny-repository) team to add the Application ID to the list of allowed applications.
- This application can then be used to generate a token in the `openalex-incremental-updater` service (see [`openalex_incremental_updater/core/auth.py`](openalex_incremental_updater/core/auth.py)) to access the DESTINY repository API.
- Create an Azure Container App:

```bash
az containerapp create --name openalex-incremental-updater-app --resource-group $RESOURCE_GROUP --environment $CONTAINER_APP_ENVIRONMENT --ingress internal --target-port 8000
```

- You will need to add Azure Key Vault read access to the application, as well as Azure Container Registry pull access.
- Add environment variables to the Azure Container App, matching those in the `.env` file. Missing environment variables will cause the container to crash on startup. The recommended workflow is to add secrets to an Azure Key Vault, and then reference those secrets in the Azure Container App environment variables. For example:

```bash
az keyvault secret set --vault-name $KEY_VAULT_NAME --name OPENALEX_API_KEY --value $OPENALEX_API_KEY
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $IMAGE_NAME:$IMAGE_TAG \
  --set-env-vars "MY_VAR=secretref:mySecret"

```

Once the above steps are completed, you can automatically deploy updates to the service via the GitHub Actions workflow in the `.github/workflows/deploy-openalex-incremental-updater.yaml` file. This will build the Docker image and push it to the Azure Container Registry, then update the Azure Container App with the new image.
