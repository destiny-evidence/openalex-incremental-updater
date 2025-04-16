import requests
import json
import io
from pathlib import Path


from loguru import logger
from tqdm import tqdm

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
    
    cursor = params["cursorMark"]
    chunk_number = 1
    total_documents_found = 0
    total_documents_to_fetch = get_total_number_of_documents(url)
    
    with tqdm(total=total_documents_to_fetch, unit="docs") as pbar:
        while True:
            
            params["cursorMark"] = cursor
        
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
            docs = data["response"]["docs"]
            chunk_file_path = output_directory / f"openalex_solr_chunk_{chunk_number:04d}.jsonl"
    
            with chunk_file_path.open("w", encoding="utf-8") as outfile:

                for doc in tqdm(docs):
                    outfile.write(json.dumps(doc))
                    outfile.write("\n")
            if not docs:
                break
            
            batch_count = len(docs)
            total_documents_found += batch_count

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
        "q": "*:*",
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
