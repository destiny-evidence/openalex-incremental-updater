# OpenAlex Incremental Updater

A service to offer incremental updates from the OpenAlex API.

## Developers

Dependency management is handled by [Poetry](https://python-poetry.org/). To install Poetry, follow the instructions on the [Poetry installation page](https://python-poetry.org/docs/#installation). Ensure you install poetry version 2.1.2 or later, as this is the version used in the Dockerfiles and Poetry will shout at you about lock file version mismatches if you use an earlier version.

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
