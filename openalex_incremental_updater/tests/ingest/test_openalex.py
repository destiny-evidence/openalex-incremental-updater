from collections.abc import Generator
from datetime import date

import httpx
import pytest
import respx
from destiny_sdk.identifiers import DOIIdentifier
from fastapi import status
from freezegun import freeze_time

from openalex_incremental_updater.ingest import CreatedOrUpdated
from openalex_incremental_updater.ingest.openalex import (
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
    safe_result_conversion,
)
from openalex_incremental_updater.models.destiny import (
    DESTINYReferenceDOIIdentifierError,
    convert_openalex_to_destiny,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "created_or_updated", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_fetch_works_filter_date_range_call_success(
    double_openalex_work_response: list[dict], created_or_updated: CreatedOrUpdated
) -> None:
    fetcher = OpenAlexDataFetcher(retries=0)
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    mock_url = "https://api.openalex.org/works"

    openalex_query = OpenAlexDataFetcher.build_range_query(
        test_date, test_date, created_or_updated
    )

    with respx.mock:
        mocked_call = respx.get(mock_url).mock(
            return_value=httpx.Response(status.HTTP_200_OK, json=expected_response)
        )

        response = fetcher.fetch_works_filter(
            openalex_filter=openalex_query,
        )
        results = [item async for item in response]
        flat_results = [work for batch in results for work in batch]
        assert mocked_call.call_count == 1
        assert flat_results == [
            convert_openalex_to_destiny(work) for work in double_openalex_work_response
        ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "created_or_updated", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
@pytest.mark.parametrize(
    "test_error_status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
async def test_fetch_works_filter_date_range_call_openalex_error(
    double_openalex_work_response: list[dict],
    created_or_updated: CreatedOrUpdated,
    test_error_status_code: int,
) -> None:
    fetcher = OpenAlexDataFetcher(retries=0)
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    mock_url = "https://api.openalex.org/works"

    test_openalex_query = OpenAlexDataFetcher.build_range_query(
        test_date, test_date, created_or_updated
    )

    with respx.mock:
        respx.get(mock_url).mock(
            return_value=httpx.Response(test_error_status_code, json=expected_response)
        )
        response = fetcher.fetch_works_filter(
            openalex_filter=test_openalex_query,
        )
        with pytest.raises(UpstreamOpenAlexError) as invalid_url_error:
            _result = [item async for item in response]

        assert isinstance(invalid_url_error.value, UpstreamOpenAlexError)
        assert str(test_error_status_code) in str(
            invalid_url_error.value
        ), "Check that the error message contains the expected status code."


@freeze_time("2025-08-19")
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
def test_build_range_query(
    ingest_type: CreatedOrUpdated, set_test_environment_variables: Generator
):
    test_start_date = date.today()
    test_end_date = test_start_date
    fetcher = OpenAlexDataFetcher()
    expected_output = f"from_{ingest_type.value}_date:{test_start_date.isoformat()},to_{ingest_type.value}_date:{test_end_date.isoformat()}"
    query = fetcher.build_range_query(test_start_date, test_end_date, ingest_type)

    assert query == expected_output


def test_safe_result_conversion_success(
    single_openalex_work_response: list[dict],
    job_report_dict: dict,
) -> None:
    errors_dict: dict[str, dict] = {}
    job_manager = job_report_dict["job_manager"]
    job_id = job_report_dict["job_id"]
    job_report = job_report_dict["report"]
    expected_converted = [convert_openalex_to_destiny(single_openalex_work_response)]
    safe_converted = safe_result_conversion(
        [single_openalex_work_response],
        errors_dict,
        report=job_report,
    )

    report_progress = job_manager.get(job_id).get("progress", {})
    report_errors = report_progress.get("errors", {})
    doi_errors = report_errors.get("doi_errors", {})
    assert all(
        converted == expected
        for converted, expected in zip(safe_converted, expected_converted, strict=False)
    ), "Converted results should match expected results"
    assert doi_errors == {}, "There should be no DOI errors"


@pytest.mark.parametrize(
    "doi_pair",
    [
        ["this/is/an/invalid_doi/", "10.1000/xyz456"],
        ["http://invalid_doi.com/12345", "10.1000/xyz456"],
        ["10.1000/xyz456=", "10.1000/xyz456"],
    ],
)
def test_safe_result_conversion_clears_invalid_doi_with_report(
    double_openalex_work_response: list[dict],
    doi_pair: list[str],
    job_report_dict: dict,
) -> None:
    errors_dict: dict = {}
    job_manager = job_report_dict["job_manager"]
    job_id = job_report_dict["job_id"]
    job_report = job_report_dict["report"]
    invalid_doi_responses = double_openalex_work_response.copy()
    for i, _ in enumerate(invalid_doi_responses):
        invalid_doi_responses[i]["doi"] = doi_pair[i]
        invalid_doi_responses[i]["ids"]["doi"] = doi_pair[i]

    invalid_dois = [doi_pair[0]]

    result_payload = invalid_doi_responses
    safe_converted = safe_result_conversion(
        result_payload,
        errors_dict,
        report=job_report,
    )
    report_progress = job_manager.get(job_id).get("progress", {})
    report_errors = report_progress.get("errors", {})

    expected_dois_present = len(doi_pair) - len(invalid_dois)

    reference_identifiers = [reference.identifiers for reference in safe_converted]

    remaining_doi_count = sum(
        isinstance(identifier, DOIIdentifier)
        for sublist in reference_identifiers
        for identifier in sublist
    )

    assert len(safe_converted) == len(
        double_openalex_work_response
    ), "All entries should be converted, invalid DOIs are just removed"
    assert expected_dois_present == remaining_doi_count, "Expect one DOI to be removed"
    assert set(report_errors.get("doi_errors", [])["examples"]) == set(
        invalid_dois
    ), "Invalid DOIs should be reported"


@pytest.mark.parametrize(
    "doi_pair",
    [
        ["this/is/an/invalid_doi/", "10.1000/xyz456"],
        ["http://invalid_doi.com/12345", "10.1000/xyz456"],
        ["10.1000/xyz456=", "10.1000/xyz456"],
    ],
)
def test_safe_result_conversion_with_invalid_doi_no_report(
    double_openalex_work_response: list[dict],
    doi_pair: list[str],
) -> None:
    errors_dict: dict[str, dict] = {}
    invalid_doi_responses = double_openalex_work_response.copy()
    for i, _ in enumerate(invalid_doi_responses):
        invalid_doi_responses[i]["doi"] = doi_pair[i]
        invalid_doi_responses[i]["ids"]["doi"] = doi_pair[i]

    invalid_dois = [doi_pair[0]]

    result_payload = invalid_doi_responses
    safe_converted = safe_result_conversion(
        result_payload,
        errors_dict,
        report=None,
    )

    expected_dois_present = len(doi_pair) - len(invalid_dois)

    reference_identifiers = [reference.identifiers for reference in safe_converted]

    remaining_doi_count = sum(
        isinstance(identifier, DOIIdentifier)
        for sublist in reference_identifiers
        for identifier in sublist
    )
    assert len(safe_converted) == len(
        double_openalex_work_response
    ), "All entries should be converted, invalid DOIs are just removed"
    assert remaining_doi_count == expected_dois_present, "Expect one DOI to be removed"


@pytest.mark.parametrize(
    "doi_pair",
    [
        ["this/is/an/invalid_doi/", "10.1000/xyz456"],
        ["http://invalid_doi.com/12345", "10.1000/xyz456"],
        ["10.1000/xyz456=", "10.1000/xyz456"],
    ],
)
def test_safe_result_conversion_clears_entire_report_on_repeated_conversion_failure(
    mocker,
    double_openalex_work_response: list[dict],
    doi_pair: list[str],
    job_report_dict: dict,
) -> None:
    errors_dict: dict = {}
    job_manager = job_report_dict["job_manager"]
    job_id = job_report_dict["job_id"]
    job_report = job_report_dict["report"]
    invalid_doi_responses = double_openalex_work_response.copy()
    for i, _ in enumerate(invalid_doi_responses):
        invalid_doi_responses[i]["doi"] = doi_pair[i]
        invalid_doi_responses[i]["ids"]["doi"] = doi_pair[i]

    invalid_dois = [doi_pair[0]]

    side_effects = iter(
        [
            DESTINYReferenceDOIIdentifierError(f"Invalid DOI: {doi_pair[0]}"),
            ValueError("Conversion failed"),
        ]
    )

    def invalid_doi_total_failure_side_effect(*args, **kwargs):
        try:
            side_effect = next(side_effects)
            raise side_effect
        except StopIteration:
            return convert_openalex_to_destiny(*args, **kwargs)

    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.convert_openalex_to_destiny",
        side_effect=invalid_doi_total_failure_side_effect,
    )
    result_payload = invalid_doi_responses

    safe_converted = safe_result_conversion(
        result_payload,
        errors_dict,
        report=job_report,
    )
    report_progress = job_manager.get(job_id).get("progress", {})
    report_errors = report_progress.get("errors", {})

    expected_dois_present = len(doi_pair) - len(invalid_dois)

    reference_identifiers = [reference.identifiers for reference in safe_converted]

    remaining_doi_count = sum(
        isinstance(identifier, DOIIdentifier)
        for sublist in reference_identifiers
        for identifier in sublist
    )

    assert (
        len(safe_converted) == expected_dois_present
    ), "All entries with invalid DOIs that continue to fail conversion should be removed"
    assert expected_dois_present == remaining_doi_count, "Expect one DOI to be removed"
    assert set(report_errors.get("doi_errors", [])["examples"]) == set(
        invalid_dois
    ), "Invalid DOIs should be reported"
    assert report_errors.get("dropped_records", {}).get("total", 0) == len(
        invalid_dois
    ), "One record should be dropped after repeated conversion failure for invalid DOIs"
