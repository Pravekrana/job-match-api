import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def create_pair(client, candidate_data, job_data):
    candidate = client.post("/candidates", json=candidate_data)
    job = client.post("/jobs", json=job_data)
    assert candidate.status_code == job.status_code == 201
    assert candidate.headers["location"] == f"/candidates/{candidate.json()['id']}"
    assert job.headers["location"] == f"/jobs/{job.json()['id']}"
    return candidate.json()["id"], job.json()["id"]


def test_round_trip_and_reverse_score_consistency(client, candidate_data, job_data):
    cid, jid = create_pair(client, candidate_data, job_data)
    assert client.get(f"/candidates/{cid}").json()["name"] == candidate_data["name"]
    assert client.get(f"/jobs/{jid}").json()["title"] == job_data["title"]
    forward = client.get(f"/candidates/{cid}/recommendations").json()[0]
    reverse = client.get(f"/jobs/{jid}/recommendations").json()[0]
    assert forward["overallScore"] == reverse["overallScore"] == 100
    assert forward["breakdown"] == reverse["breakdown"]
    assert forward["job"]["id"] == jid
    assert reverse["candidate"]["id"] == cid


def test_filter_then_rank_then_limit(client, candidate_data, job_data):
    job_data["location"] = "Delhi"
    cid, weak = create_pair(client, candidate_data, job_data)
    job_data["location"] = "Bengaluru"
    strong = client.post("/jobs", json=job_data).json()["id"]
    tie = client.post("/jobs", json=job_data).json()["id"]
    job_data["requiredSkills"].append({"name": "Rust", "importance": "must-have"})
    excluded = client.post("/jobs", json=job_data).json()["id"]
    results = client.get(f"/candidates/{cid}/recommendations").json()
    assert [r["job"]["id"] for r in results] == [strong, tie, weak]
    assert excluded not in [r["job"]["id"] for r in results]
    top = client.get(f"/candidates/{cid}/recommendations?limit=1").json()
    assert [r["job"]["id"] for r in top] == [strong]


def test_reverse_filter_rank_and_limit(client, candidate_data, job_data):
    candidate_data["yearsOfExperience"] = 1
    weak, jid = create_pair(client, candidate_data, job_data)
    candidate_data["yearsOfExperience"] = 3
    strong = client.post("/candidates", json=candidate_data).json()["id"]
    tie = client.post("/candidates", json=candidate_data).json()["id"]
    candidate_data["skills"] = []
    client.post("/candidates", json=candidate_data)
    results = client.get(f"/jobs/{jid}/recommendations").json()
    assert [r["candidate"]["id"] for r in results] == [strong, tie, weak]
    assert len(client.get(f"/jobs/{jid}/recommendations?limit=1").json()) == 1


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
def test_empty_recommendations(client, candidate_data, job_data, resource):
    data = candidate_data if resource == "candidates" else job_data
    rid = client.post(f"/{resource}", json=data).json()["id"]
    assert client.get(f"/{resource}/{rid}/recommendations").json() == []


@pytest.mark.parametrize(
    "path",
    [
        "/candidates/999",
        "/jobs/999",
        "/candidates/999/recommendations",
        "/jobs/999/recommendations",
    ],
)
def test_unknown_resource(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=-1",
        "limit=101",
        "limit=1.5",
        "limit=abc",
        "skillsWeight=51",
        "salaryWeight=-1",
        "skillsWeight=NaN",
        "skillsWeight=101",
        "skillsWeight=50.5",
    ],
)
@pytest.mark.parametrize("resource", ["candidates", "jobs"])
def test_invalid_query(client, candidate_data, job_data, query, resource):
    cid, jid = create_pair(client, candidate_data, job_data)
    rid = cid if resource == "candidates" else jid
    assert client.get(f"/{resource}/{rid}/recommendations?{query}").status_code == 422


def test_custom_weights_change_ranking(client, candidate_data, job_data):
    job_data["salaryRange"] = {"min": 0, "max": 1}
    cid, local = create_pair(client, candidate_data, job_data)
    job_data.update(location="Delhi", salaryRange={"min": 100000, "max": 140000})
    well_paid = client.post("/jobs", json=job_data).json()["id"]
    query = "skillsWeight=0&experienceWeight=0&locationWeight=0&salaryWeight=100"
    results = client.get(f"/candidates/{cid}/recommendations?{query}").json()
    assert [r["job"]["id"] for r in results] == [well_paid, local]
    assert [r["overallScore"] for r in results] == [100, 0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "   "),
        ("skills", [""]),
        ("skills", "Python"),
        ("yearsOfExperience", -1),
        ("yearsOfExperience", True),
        ("expectedSalary", -1),
        ("expectedSalary", "NaN"),
        ("expectedSalary", "100000"),
        ("location", ""),
        ("unexpectedField", "oops"),
        ("id", 123),
    ],
)
def test_invalid_candidate(client, candidate_data, field, value):
    candidate_data[field] = value
    assert client.post("/candidates", json=candidate_data).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("salaryRange", {"min": 10, "max": 1}),
        ("salaryRange", {"min": -1, "max": 1}),
        ("remoteAllowed", "true"),
        ("minYearsExperience", -1),
        ("requiredSkills", [{"name": "python", "importance": "required"}]),
        (
            "requiredSkills",
            [
                {"name": "python", "importance": "must-have"},
                {"name": " PYTHON ", "importance": "nice-to-have"},
            ],
        ),
    ],
)
def test_invalid_job(client, job_data, field, value):
    job_data[field] = value
    assert client.post("/jobs", json=job_data).status_code == 422


def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    schema = client.get("/openapi.json").json()
    assert "/jobs/{job_id}/recommendations" in schema["paths"]
    assert client.get("/docs").status_code == 200


def test_sqlite_data_survives_app_restart(tmp_path, candidate_data, job_data):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    with TestClient(create_app(url)) as first:
        cid, jid = create_pair(first, candidate_data, job_data)
    with TestClient(create_app(url)) as restarted:
        assert restarted.get(f"/candidates/{cid}").status_code == 200
        assert restarted.get(f"/jobs/{jid}").status_code == 200
        assert restarted.get(f"/candidates/{cid}/recommendations").json()[0]["overallScore"] == 100
