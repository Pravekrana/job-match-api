import pytest


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
def test_minimum_score(client, candidate_data, job_data, resource):
    cid = client.post("/candidates", json=candidate_data).json()["id"]
    jid = client.post("/jobs", json=job_data).json()["id"]
    rid = cid if resource == "candidates" else jid
    path = f"/{resource}/{rid}/recommendations"
    assert client.get(f"{path}?minScore=100").json()[0]["overallScore"] == 100
    candidate_data["location"] = "Delhi"
    job_data["location"] = "Delhi"
    opposite = "jobs" if resource == "candidates" else "candidates"
    data = job_data if opposite == "jobs" else candidate_data
    client.post(f"/{opposite}", json=data)
    assert len(client.get(path).json()) == 2
    assert len(client.get(f"{path}?minScore=85").json()) == 2
    assert len(client.get(f"{path}?minScore=85.01&limit=1").json()) == 1
    query = "skillsWeight=0&experienceWeight=0&locationWeight=100&salaryWeight=0"
    assert len(client.get(f"{path}?{query}&minScore=1").json()) == 1


@pytest.mark.parametrize("resource", ["candidates", "jobs"])
@pytest.mark.parametrize("value", ["-1", "101", "NaN", "inf", "abc"])
def test_invalid_minimum_score(client, resource, value):
    assert client.get(f"/{resource}/1/recommendations?minScore={value}").status_code == 422
