"""Module for requesting all stored content in a Solr instance via the Solr API."""

import json
from pathlib import Path

import requests
from loguru import logger
from requests.adapters import HTTPAdapter, Retry
from tqdm import tqdm

SOLR_URL = "http://localhost:8983/solr/openalex_replica/select"
ROWS = 10000


def get_last_completed_chunk(metadata_directory: Path) -> int:
    """
    Read metadata directory and returns the last completed chunk number.

    Args:
        metadata_directory (Path): Path to the metadata directory.

    Returns:
        int: The last completed chunk number.

    """
    meta_files = list(metadata_directory.glob("*meta.json"))

    max_chunk = 0

    for meta in meta_files:
        base = meta.stem
        part = base.replace("openalex_solr_chunk_", "")
        chunk_index_string = part.replace(".meta", "")
        try:
            index = int(chunk_index_string)
            max_chunk = max(max_chunk, index)
        except ValueError:
            pass
    return max_chunk


def get_resume_cursor(chunk_number: int, metadata_directory: Path) -> str:
    """
    Read sidecar file for chunk_number and returns the stored cursorMark.

    Args:
        chunk_number (int): Index of the chunk to resume from.
        metadata_directory (Path): Path to the metadata directory.

    Returns:
        str: The stored cursorMark for the chunk.

    """
    sidecar_path = (
        metadata_directory / f"openalex_solr_chunk_{chunk_number:04d}.meta.json"
    )

    with sidecar_path.open("r", encoding="utf-8") as meta_file:
        data = json.load(meta_file)
    return data.get("nextCursorMark")


def get_total_number_of_documents(solr_url: str, params: dict) -> int:
    """
    Fetch the total number of documents in the Solr collection.

    Args:
        solr_url (str): The URL of the Solr instance.
        params (dict): The parameters for the Solr query.

    Returns:
        int: The total number of documents in the collection.

    """
    totals_params = params.copy()
    totals_params["rows"] = 0
    response = requests.get(solr_url, params=totals_params, timeout=300)
    response.raise_for_status()
    data = response.json()
    logger.info(f"{data['response']['numFound']} records found")
    return data["response"]["numFound"]


def run_solr_query(url: str, params: dict, output_directory: Path) -> None:
    """
    Run a Solr query and save results to files.

    Args:
        url (str): The URL of the Solr instance.
        params (dict): The parameters for the Solr query.
        output_directory (Path): The directory to save the output files.

    """
    output_directory.mkdir(parents=True, exist_ok=True)
    metadata_directory = output_directory / "meta"
    metadata_directory.mkdir(parents=True, exist_ok=True)

    last_chunk_completed = get_last_completed_chunk(metadata_directory)
    if last_chunk_completed > 0:
        cursor = get_resume_cursor(last_chunk_completed, metadata_directory)
        chunk_number = last_chunk_completed + 1
        logger.info(f"Resuming fetch from chunk {chunk_number} with {cursor=}")
    else:
        logger.info("Starting new run from scratch.")
        cursor = params["cursorMark"]
        chunk_number = 1

    documents_already_fetched = last_chunk_completed * ROWS
    total_documents_to_fetch = (
        get_total_number_of_documents(url, params) - documents_already_fetched
    )

    max_retries = 15
    backoff_factor = 0.1
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))

    logger.info("Querying Solr...")
    with tqdm(total=total_documents_to_fetch, unit="docs") as pbar:
        while True:
            params["cursorMark"] = cursor
            response = session.get(url, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            try:
                docs = data["response"]["docs"]
            except KeyError:
                logger.error("No docs found in response! Exiting.")
                break
            chunk_file_path = (
                output_directory / f"openalex_solr_chunk_{chunk_number:04d}.jsonl"
            )

            if not docs:
                break

            with chunk_file_path.open("w", encoding="utf-8") as outfile:
                for doc in docs:
                    outfile.write(json.dumps(doc))
                    outfile.write("\n")

            batch_count = len(docs)

            pbar.update(batch_count)
            pbar.set_postfix({"chunks": chunk_number, "last_batch": batch_count})
            next_cursor = data.get("nextCursorMark")

            sidecar_file = (
                metadata_directory / f"openalex_solr_chunk_{chunk_number:04d}.meta.json"
            )
            with sidecar_file.open("w", encoding="utf-8") as metadata_file:
                json.dump({"nextCursorMark": next_cursor}, metadata_file)

            if not next_cursor or next_cursor == cursor:
                logger.info("Reached the end of the collection")
                break

            cursor = next_cursor
            chunk_number += 1


def solr_to_files() -> None:
    """Run a complex Solr query to fetch all required documents and save them to files."""
    logger.info("Starting Solr query...")
    query_file = Path.cwd() / "solr_search_query.txt"
    if not query_file.exists():
        logger.error(f"Query file {query_file} does not exist.")
        return
    with query_file.open("r", encoding="utf-8") as qf:
        full_query = qf.read()
    params = {
        "q": full_query,
        "q.op": "AND",
        "rows": ROWS,
        "defType": "lucene",
        "df": "title_abstract",
        "wt": "json",
        "fl": "*",
        "cursorMark": "*",
        "sort": "created_date desc,id asc",
    }

    output_directory = Path.cwd() / "solr_data_tim_query_subset_json"

    run_solr_query(SOLR_URL, params, output_directory)

    logger.info("Export complete.")


if __name__ == "__main__":
    solr_to_files()
