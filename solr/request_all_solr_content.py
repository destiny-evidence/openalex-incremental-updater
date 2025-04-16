import requests
from requests.adapters import HTTPAdapter, Retry
import json
import io
from pathlib import Path


from loguru import logger
from tqdm import tqdm


def get_last_completed_chunk(metadata_directory: Path) -> int:
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

def get_resume_cursor(chunk_number: int, metadata_directory: Path):
    """Reads sidecar file for chunk_number and returns the stored cursorMark."""
    sidecar_path = metadata_directory / f"openalex_solr_chunk_{chunk_number:04d}.meta.json"

    with sidecar_path.open("r", encoding="utf-8") as meta_file:
        data = json.load(meta_file)
    return data.get("nextCursorMark")


def get_total_number_of_documents(solr_url: str):

    params = {
        "q": "*:*",
        "rows": 0,
        "wt": json
    }
    response = requests.get(solr_url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["response"]["numFound"]


def run_solr_query(url: str, params: dict, output_directory: Path):

    output_directory.mkdir(parents=True, exist_ok=True)
    metadata_directory = output_directory / "meta"
    metadata_directory.mkdir(parents=True, exist_ok=True)

    last_chunk_completed = get_last_completed_chunk(metadata_directory)
    if last_chunk_completed > 0:
        cursor = get_resume_cursor(last_chunk_completed, metadata_directory)
        chunk_number = last_chunk_completed + 1
        logger.info(f"Resuming fetch from chunk {chunk_number} with {cursor=}")
    else:
        logger.info(f"Starting new run from scratch.")
        cursor = params["cursorMark"]
        chunk_number = 1


    total_documents_to_fetch = get_total_number_of_documents(url)
    
    with tqdm(total=total_documents_to_fetch, unit="docs") as pbar:
        while True:

            max_retries = 5
            backoff_factor = 0.1
            params["cursorMark"] = cursor
            session = requests.Session()
            retries = Retry(total=max_retries, backoff_factor=backoff_factor, status_forcelist=[500, 502, 503, 504])
            session.mount("http://", HTTPAdapter(max_retries=retries))

            response = session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
                
                

            try:
                docs = data["response"]["docs"]
            except KeyError:
                logger.error("No docs found in response! Exiting.")
                break
            chunk_file_path = output_directory / f"openalex_solr_chunk_{chunk_number:04d}.jsonl"
    
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

            sidecar_file = metadata_directory / f"openalex_solr_chunk_{chunk_number:04d}.meta.json"
            with sidecar_file.open("w", encoding="utf-8") as metadata_file:
                json.dump({"nextCursorMark": next_cursor}, metadata_file)
        
            if not next_cursor or next_cursor == cursor:
                logger.info("Reached the end of the collection")
                break
        
            cursor = next_cursor
            chunk_number += 1
    

def solr_to_files():
    SOLR_URL = "http://localhost:8983/solr/openalex_replica/select"
    ROWS = 20000

    params = {
        "q": "{!cache=false}*:*",
        "rows": ROWS,
        "wt": "json",
        "cursorMark": "*",
        "sort": "created_date desc,id asc"
    }

    output_directory = Path.cwd() / "solr_data_json"
    
    run_solr_query(SOLR_URL, params, output_directory)

    logger.info("Export complete.")

if __name__ == "__main__":
    solr_to_files()
