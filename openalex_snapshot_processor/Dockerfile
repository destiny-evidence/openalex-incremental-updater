FROM apache/airflow:3.1.7-python3.13

USER root

COPY ../openalex_incremental_updater /opt/packages/openalex_incremental_updater
COPY ../refresh_requester /opt/packages/refresh_requester
COPY ../openalex_snapshot_processor /opt/packages/openalex_snapshot_processor

RUN chown -R airflow /opt/packages

USER airflow

RUN pip install\
    msal \
    psycopg2-binary \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.1.7/constraints-3.13.txt"
RUN pip install --no-cache-dir --no-deps \
    /opt/packages/openalex_incremental_updater \
    /opt/packages/refresh_requester \
    /opt/packages/openalex_snapshot_processor
