import json
import gzip
import math
import multiprocessing

from concurrent.futures import ProcessPoolExecutor
from enum import Enum
from loguru import logger
from pathlib import Path
from pydantic import (
    BaseModel,
    Field,
)
from tqdm import tqdm
from typing import Literal


logger.add("schema_conversion_processing.log", rotation="10 MB", level="INFO", enqueue=True)

class Visibility(str, Enum):
    """
    The visibility of a data element in the repository.

    This is used to manage whether information should be publicly available or
    restricted (generally due to copyright constraints from publishers).

    TODO: Implement data governance layer to manage this.

    **Allowed values**:

    - `public`: Visible to the general public without authentication.
    - `restricted`: Requires authentication to be visible.
    - `hidden`: Is not visible, but may be passed to data mining processes.
    """

    PUBLIC = "public"
    RESTRICTED = "restricted"
    HIDDEN = "hidden"

class ExternalIdentifierType(str, Enum):
    """
    The type of identifier used to identify a reference.

    This is used to identify the type of identifier used in the `ExternalIdentifier`
    class.
    **Allowed values**:
    - `doi`: A DOI (Digital Object Identifier) which is a unique identifier for a
        document.
    - `pmid`: A PubMed ID which is a unique identifier for a document in PubMed.
    - `openalex`: An OpenAlex ID which is a unique identifier for a document in
        OpenAlex.
    - `other`: Any other identifier not defined. This should be used sparingly.
    """

    DOI = "doi"
    PM_ID = "pm_id"
    OPEN_ALEX = "open_alex"
    OTHER = "other"


class EnhancementType(str, Enum):
    """
    The type of enhancement.

    This is used to identify the type of enhancement in the `Enhancement` class.

    **Allowed values**:
    - `bibliographic`: Bibliographic metadata.
    - `abstract`: The abstract of a reference.
    - `annotation`: A free-form enhancement for tagging with labels.
    - `locations`: Locations where the reference can be found.
    """

    BIBLIOGRAPHIC = "bibliographic"
    ABSTRACT = "abstract"
    ANNOTATION = "annotation"
    LOCATION = "location"


class AbstractProcessType(str, Enum):
    """
    The process used to acquyire the abstract.

    **Allowed values**:
    - `uninverted`
    - `closed_api`
    - `other`
    """

    UNINVERTED = "uninverted"
    CLOSED_API = "closed_api"
    OTHER = "other"


class AbstractContentEnhancement(BaseModel):
    """
    An enhancement which is specific to the abstract of a reference.

    This is separate from the `BibliographicMetadata` for two reasons:

    1. Abstracts are increasingly missing from sources like OpenAlex, and may be
    backfilled from other sources, without the bibliographic metadata.
    2. They are also subject to copyright limitations in ways which metadata are
    not, and thus need separate visibility controls.
    """

    enhancement_type: Literal[EnhancementType.ABSTRACT] = EnhancementType.ABSTRACT
    process: AbstractProcessType = Field(
        description="The process used to acquire the abstract."
    )
    abstract: str = Field(description="The abstract of the reference.")

    
class DestinyOpenAlexWork(BaseModel):
    """Schema representing a work in the Destiny system."""

    visibility: Visibility = Field(
        default=Visibility.PUBLIC,
        description="The visibility of the work in the Destiny system.",
    )
    identifiers: list[dict] = Field(
        default_factory=list[dict],
        description="A list of `ExternalIdentifiers` for the Reference",
    )
    enhancements: list[dict] = Field(
        default_factory=list[dict],
        description="A list of enhancements for the reference",
    )

def convert_solr_to_destiny(solr_document: dict) -> DestinyOpenAlexWork:
    """
    Convert a Solr document to a Destiny OpenAlex work.

    Args:
        solr_document (dict): The Solr document to convert.

    Returns:
        DestinyOpenAlexWork: The converted Destiny OpenAlex work.

    """
    processor_version = "initial_solr_import"
    doi = solr_document.get("doi")
    openalex_id = solr_document.get("id")
    microsoft_academic_graph = solr_document.get("mag")
    pubmed_id = solr_document.get("pmid")
    pubmed_central_id = solr_document.get("pmcid")

    authorships_list_of_dicts = json.loads(solr_document.get("authorships", "[]")) # type: list[dict]

    publisher = solr_document.get("publisher")
    publication_date = solr_document.get("publication_date")
    publication_year = solr_document.get("publication_year")

    is_retracted = solr_document.get("is_retracted")

    locations_list_of_dicts = json.loads(solr_document.get("locations", "[]"))
    topics_list_of_dicts = json.loads(solr_document.get("topics", "[]"))

    destiny_work = DestinyOpenAlexWork(
        visibility=Visibility.PUBLIC if not is_retracted else Visibility.HIDDEN,
        identifiers=[
            {
                "identifier_type": ExternalIdentifierType.DOI.value,
                "identifier": doi,
            },
            {
                "identifier_type": ExternalIdentifierType.OPEN_ALEX.value,
                "identifier": openalex_id,
            },
            {
                "identifier_type": ExternalIdentifierType.PM_ID.value,
                "identifier": pubmed_id,
            },
        ],
        enhancements=[
            {
                "source": "pik_solr",
                "processor_version": processor_version,
                "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                    "title": solr_document.get("title"),
                },
            },
            {
                "source": "pik_solr",
                "processor_version": processor_version,
                "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                    "authorship": [
                        {
                            "display_name": author_dict["author"].get("display_name")
                            if author_dict["author"]
                            else None,
                            "orcid": author_dict["author"].get("orcid")
                            if author_dict["author"]
                            else None,
                            "position": author_dict.get("author_position")
                            if author_dict
                            else None,
                        }
                        for author_dict in authorships_list_of_dicts or {}
                    ],
                    "cited_by_count": solr_document.get("cited_by_count"),
                    "created_date": solr_document.get("created_date"),
                    "publication_date": publication_date,
                    "publication_year": publication_year,
                    "publisher": publisher,
                },
            },
            {
                "source": "pik_solr",
                "processor_version": processor_version,
                "enhancement_type": EnhancementType.ABSTRACT.value,
                "content": {
                    "enhancement_type": EnhancementType.ABSTRACT.value,
                    "process": AbstractProcessType.OTHER.value,
                    "abstract": solr_document.get("abstract"),
                },
            },
            {
                "source": "pik_solr",
                "processor_version": processor_version,
                "enhancement_type": EnhancementType.LOCATION.value,
                "content": {
                    "enhancement_type": EnhancementType.LOCATION.value,
                    "locations": [
                        {
                            "is_oa": location.get("is_oa"),
                            "version": location.get("version"),
                            "landing_page_url": location.get("landing_page_url"),
                            "pdf_url": location.get("pdf_url"),
                            "license": location.get("license"),
                        }
                        for location in locations_list_of_dicts or {}
                    ],
                },
            },
            {
                "source": "pik_solr",
                "processor_version": processor_version,
                "enhancement_type": EnhancementType.ANNOTATION.value,
                "content": {
                    "enhancement_type": EnhancementType.ANNOTATION.value,
                    "annotations": [
                        {
                            "annotation_type": "openalex:topic",
                            "label": annotation["display_name"],
                            "data": annotation,
                        }
                        for annotation in topics_list_of_dicts or {}
                    ],
                },
            },
        ],
    )
    if microsoft_academic_graph:
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": microsoft_academic_graph,
            }
        )
    if pubmed_central_id:
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": pubmed_central_id,
            }
        )
    return destiny_work

def transform_batch(batch: list[dict]) -> list[dict]:
    return [convert_solr_to_destiny(solr_document) for solr_document in batch]

def chunkify(data: list[dict], num_chunks: int) -> list[list[dict]]:
    chunk_size = math.ceil(len(data) / num_chunks)
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def process_file_full(
    input_path: Path,
    output_path: Path,
    compress: bool = False,
    workers: int = 4
) -> None:
    logger.debug(f"Loading file into memory: {input_path.name}")
    with input_path.open('r', encoding='utf-8') as f:
        lines = f.readlines()

    records = [json.loads(line) for line in lines]
    chunks = chunkify(records, workers)

    logger.debug(f"Transforming {len(records)} records in parallel with {workers} workers")
    with ProcessPoolExecutor(max_workers=workers) as executor:
        processed_chunks = list(executor.map(transform_batch, chunks))

    output_data = [rec for chunk in processed_chunks for rec in chunk]

    open_fn = gzip.open if compress else open
    mode = 'wt' if compress else 'w'
    logger.debug(f"Writing output to {output_path.name} ({'compressed' if compress else 'uncompressed'})")
    with open_fn(output_path, mode, encoding='utf-8') as f:
        for record in output_data:
            f.write(record.model_dump_json() + '\n')

    logger.success(f"Finished processing {input_path.name} → {output_path.name}")


def wrapper(args: tuple[Path, Path, bool, int]) -> None:
    input_path, output_path, compress_flag, cpu_workers = args
    try:
        process_file_full(input_path, output_path, compress=compress_flag, workers=cpu_workers)
    except Exception as e:
        logger.exception(f"Error processing {input_path.name}: {e}")

def process_all_files(
    input_dir: Path,
    output_dir: Path,
    compress: bool = False,
    file_workers: int = 2,
    cpu_workers_per_file: int = 4
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    file_args = []
    for input_file in sorted(input_dir.glob("*.jsonl")):
        suffix = ".jsonl.gz" if compress else ".jsonl"
        output_file = output_dir / (input_file.stem + suffix)
        file_args.append((input_file, output_file, compress, cpu_workers_per_file))

        
    logger.info(f"Starting parallel processing of {len(file_args)} files with {file_workers} file workers")
    with ProcessPoolExecutor(max_workers=file_workers) as executor:
        list(tqdm(executor.map(wrapper, file_args), total=len(file_args), desc="All Files"))

    logger.success("All files processed successfully.")

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Parallel JSONL processor with in-memory loading.")
    parser.add_argument("input_dir", type=Path, help="Directory containing input .jsonl files")
    parser.add_argument("output_dir", type=Path, help="Directory to store processed output")
    parser.add_argument("--compress", action="store_true", help="Compress output files with gzip")
    parser.add_argument("--file-workers", type=int, default=2, help="Number of parallel files to process")
    parser.add_argument("--cpu-workers", type=int, default=multiprocessing.cpu_count() // 2,
                        help="CPU cores to use per file")

    args = parser.parse_args()
    process_all_files(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        compress=args.compress,
        file_workers=args.file_workers,
        cpu_workers_per_file=args.cpu_workers
    )
