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


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
@pytest.mark.parametrize("offset", [2**63 - 1, 2**63, 99999999999999999999])
def test_huge_offsets_are_empty(client, candidate_data, job_data, resource, offset):
    data = candidate_data if resource == "candidates" else job_data
    assert client.post(f"/{resource}", json=data).status_code == 201
    response = client.get(f"/{resource}?offset={offset}")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
def test_maximum_page_size(client, candidate_data, job_data, resource):
    data = candidate_data if resource == "candidates" else job_data
    ids = []
    for _ in range(101):
        response = client.post(f"/{resource}", json=data)
        assert response.status_code == 201
        ids.append(response.json()["id"])
    response = client.get(f"/{resource}?limit=100")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ids[:100]
    assert client.get(f"/{resource}?offset=100&limit=100").json()[0]["id"] == ids[100]
