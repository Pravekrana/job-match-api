import pytest


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
def test_listing_pages(client, candidate_data, job_data, resource):
    data = candidate_data if resource == "candidates" else job_data
    assert client.get(f"/{resource}").json() == []
    records = [client.post(f"/{resource}", json=data).json() for _ in range(3)]
    assert client.get(f"/{resource}").json() == records
    assert client.get(f"/{resource}?offset=1&limit=1").json() == records[1:2]
    assert client.get(f"/{resource}?offset=3").json() == []


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
@pytest.mark.parametrize("query", ["offset=-1", "offset=1.5", "limit=0", "limit=101"])
def test_listing_validation(client, resource, query):
    assert client.get(f"/{resource}?{query}").status_code == 422
