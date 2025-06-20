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

- `CORS_ORIGINS`. This should be a comma-separated list of origins that are allowed to access the API. This can be set to `http://localhost:3000` for now. _To be deprecated in future versions._
- `USER_EMAIL`. Email address of the user making the request against the OpenAlex API. Needed for the free tier, which we're not using. _To be deprecated in future versions._
- `OPENALEX_API_KEY`. OpenAlex API key.
- `AZURE_AUTH_ENVIRONMENT_ID`. The Application ID of the Azure environment in which the DESTINY repository is running. This will be different for `dev`, `staging` and `prod` environments, and must be obtained from the [destiny-repsository](https://github.com/destiny-evidence/destiny-repository) team.
- `APP_REGISTRATION_APP_ID`. The Application (client) ID of the Azure Application Registration that has access to a deployment of the DESTINY repository API. See below for details on how to set this up.
- `APP_REGISTRATION_SECRET`. The secret created for the Azure Application Registration that has access to a deployment of the DESTINY repository API. This is used to authenticate the application when requesting tokens for the DESTINY repository API.
- `TENANT_ID`. The tenant ID of the Azure Active Directory in which the Application Registration was created. This should be the same tenant ID as the one used for the DESTINY repository API, and does not need to match the tenant ID for the `openalex-incremental-updater` service Azure Container App.

(see `.env.example` for an example of how to format this file).

### Running locally

To run the service locally, run the following command from the root of the repository:

```bash
uvicorn openalex_incremental_updater.main:app --reload
```

By default, this will run on port 8000. Automatically generated API documentation will be available at `http://localhost:8000/docs`. You can change the port by modifying the command above with the `--port` flag.

### Containerisation

A `Dockerfile` is provided to build a container image for the service. To build the image, run the build script provided in the root of the repository:

```bash
./build_openalex_incremental_updater.sh
```

Then run the built image within a container with:

```bash
docker run -p 8000:8000 --name openalex-app --env-file .env openalex-incremental-updater
```

referring to the `.env` file in openalex_incremental_updater/.env. This will run the service in a container, mapping port 8000 on the host to port 8000 in the container. You can change the port by modifying the `-p` flag in the command above.

Alternatively, use the convenience script provided in the root of the repository:

```bash
./run_openalex_incremental_updater.sh
```

This is currently set up to run the service on port 8000, but this can be changed by modifying the `Dockerfile` and the `docker run` command. This may also be handled in future by container orchestration, along with secrets management.

### Testing

Tests are provided in the `tests` directory and use the [pytest](https://pypi.org/project/pytest/) library. To run the tests, ensure you have the `poetry` package installed, and run:

```bash
poetry run pytest --cov=openalex_incremental_updater
```

from this directory.

## Azure Deployment

- Create an Application Registration in your Azure Tenant as documented in the [Azure Samples documentation](https://github.com/Azure-Samples/ms-identity-python-daemon/tree/master/1-Call-MsGraph-WithSecret). Note down the Application (client) ID and Directory (tenant) ID
- Create a client secret for the application and note it down.
- Contact the [destiny-repository](https://github.com/destiny-evidence/destiny-repository) team to add the Application ID to the list of allowed applications.
- This application can then be used to generate a token in the `openalex-incremental-updater` service (see [`openalex_incremental_updater/core/auth.py`](openalex_incremental_updater/core/auth.py)) to access the DESTINY repository API.
- Create an Azure Container App Environment if you don't already have one:

```bash
az containerapp env create --name openalex-incremental-updater-env --resource-group $RESOURCE_GROUP --location $LOCATION
```

- Create an Azure Container App within the previously created Container App Environment.

```bash
az containerapp create --name openalex-incremental-updater-app --resource-group $RESOURCE_GROUP --environment $CONTAINER_APP_ENVIRONMENT --ingress internal --target-port 8000
```

- Check that the app can only be accessed from within the Azure Container App Environment. This is important for security, as the service should not be publicly accessible.

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
