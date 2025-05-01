import requests
from requests.adapters import HTTPAdapter, Retry
import json
import io
from pathlib import Path


from loguru import logger
from tqdm import tqdm

SOLR_URL = "http://localhost:8983/solr/openalex_replica/select"
ROWS = 10000

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


def get_total_number_of_documents(solr_url: str, params: dict):
    totals_params = params.copy()
    totals_params["rows"] = 0
    response = requests.get(solr_url, params=totals_params)
    response.raise_for_status()
    data = response.json()
    logger.info(f"{data['response']['numFound']} records found")
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

    documents_already_fetched = last_chunk_completed * ROWS
    total_documents_to_fetch = get_total_number_of_documents(url, params) - documents_already_fetched

    
    max_retries = 15
    backoff_factor = 0.1
    session = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=backoff_factor, status_forcelist=[500, 502, 503, 504])
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
    full_query = "(\n  (climat* OR \"global warming\" OR \"greenhouse effect\" OR \"greenhouse effects\" OR \"greenhouse gas\" OR \"greenhouse gases\" OR \"greenhouse gas emissions\" OR \"greenhouse emissions\" OR \"GHG emissions\" OR \"GHGE\" OR temperature* OR precipitat* OR rainfall OR \"heat index\" OR \"heat indices\" OR \"extreme heat event\" OR \"extreme heat events\" OR \"heat-wave\" OR heatwave OR \"extreme-cold*\" OR \"cold index\" OR \"cold indices\" OR humidity OR drought* OR hydroclim* OR monsoon OR \"el nino\" OR ENSO OR \"sea surface temperature\" OR \"sea surface temperatures\" OR SST OR snowmelt* OR flood* OR storm* OR cyclone* OR hurricane* OR typhoon* OR \"sea-level\" OR \"sea level\" OR wildfire* OR \"wild-fire\" OR \"forest-fire\" OR \"forest fire\" OR \"forest fires\")\n  OR\n  ({!surround v=\"(disaster) 3N (risk OR management OR manage OR managing OR natural)\"})\n  OR\n  (({!surround v=\"extreme 3N event\"}) NOT paleo)\n  OR\n\n    ({!surround v=\"(hydrochloroflourocarbons OR pm2.5 OR ammonia OR VOCs OR nox OR hydrochloroflourocarbon OR HFCs OR SO4 OR carbon OR n20 OR halogen OR chlorocarbon OR pm25 OR nh3 OR SOX OR O3 OR ccl4 OR NMVOC OR SO2 OR HFC OR CO OR nitrous OR methane OR ch4 OR co2 OR sulphur OR VOC OR ozone OR chlorocarbons) 3N (emissions OR emitter OR emitting OR mitigate OR emission OR mitigation)\"})\n)\nAND\n(\n  (health OR wellbeing OR \"well-being\" OR ill OR illness OR disease* OR syndrome* OR infect* OR medical* OR mortality OR DALY OR morbidity OR injur* OR death* OR hospital* OR acciden* OR emergency OR emergent OR doctor OR GP OR obes* OR overweight OR \"over-weight\" OR underweight OR \"under-weight\" OR hunger OR stunting OR wasting OR undernourish* OR undernutrition OR anthropometr* OR malnutrition OR malnour* OR anemia OR anaemia OR \"micro-nutrient*\" OR hypertension OR \"blood pressure\" OR stroke OR renovascular OR cardiovascular OR cerebrovascular OR (CVD NOT (vapor OR vapour)) OR \"heart disease\" OR Isch*emic OR cardio*vascular OR \"heart attack\" OR \"heart attacks\" OR coronary OR CHD OR diabet* OR CKD OR renal OR cancer OR kidney OR lithogenes* OR skin OR fever* OR renal* OR rash* OR eczema* OR \"thermal stress\" OR hypertherm* OR hypotherm* OR pre*term OR stillbirth OR birth*weight OR LBW OR maternal OR pregnan* OR gestation* OR \"pre-eclampsia\" OR \"preeclampsia\" OR sepsis OR oligohydramnios OR placenta* OR haemorrhage OR hemorrhage OR malaria OR dengue* OR mosquito* OR chikungunya OR leishmaniasis OR encephalit* OR vector-borne OR pathogen OR zoonos* OR zika* OR \"west nile\" OR onchocerciasis OR filiariasis OR waterborne OR diarrhoeal OR diarrheal OR gastro* OR (enteric NOT (fermentation OR \"enteric CH4\" OR \"enteric methane\")) OR \"vibrio bacteria\" OR cyanobacteria OR parasit* OR borrelia OR paraly* OR neurotoxi* OR viral OR rotavirus OR noravirus OR hantavirus OR cholera OR protozoa* OR lyme OR tick*borne OR salmonella OR giardia OR shigella OR campylobacter OR food*borne OR aflatoxin OR poison* OR ciguatera OR respiratory OR allerg* OR lung* OR asthma* OR bronchi* OR pulmonary* OR COPD OR rhinitis OR wheez* OR mental OR depress* OR anxi* OR PTSD OR psycho* OR \"post*trauma*\" OR \"pre-trauma*\" OR \"pretrauma*\" OR suicide*\n  ) OR\n  ({!surround v=\"(heat) 3N (stress OR fatigue OR burn OR burns OR stroke OR exhaustion OR cramp)\"} NOT cattle\n  )\n)"
    params = {
        "q": full_query,
        "q.op": "AND",
        "rows": ROWS,
        "defType": "lucene",
        "df": "title_abstract",
        "wt": "json",
        "fl": "*",
        "cursorMark": "*",
        "sort": "created_date desc,id asc"
    }

    output_directory = Path.cwd() / "solr_data_tim_query_subset_json"
    
    run_solr_query(SOLR_URL, params, output_directory)

    logger.info("Export complete.")

if __name__ == "__main__":
    solr_to_files()
