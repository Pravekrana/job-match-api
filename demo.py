"""Create example data against a running API and print its ranked recommendations."""

import argparse
import json
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    def request(path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(
            args.base_url.rstrip("/") + path,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    candidate = request(
        "/candidates",
        {
            "name": "Asha Rao",
            "skills": ["Python", "SQL"],
            "yearsOfExperience": 3,
            "location": "Bengaluru",
            "expectedSalary": 100000,
        },
    )
    base_job = {
        "title": "Backend Engineer",
        "requiredSkills": [
            {"name": "Python", "importance": "must-have"},
            {"name": "SQL", "importance": "nice-to-have"},
        ],
        "minYearsExperience": 3,
        "location": "Bengaluru",
        "salaryRange": {"min": 100000, "max": 140000},
        "remoteAllowed": False,
    }
    jobs = [
        base_job,
        {
            **base_job,
            "title": "Remote Backend Engineer",
            "location": "Delhi",
            "remoteAllowed": True,
        },
        {**base_job, "title": "Senior Backend Engineer", "minYearsExperience": 6},
        {
            **base_job,
            "title": "Rust Engineer (excluded)",
            "requiredSkills": [
                {"name": "Rust", "importance": "must-have"},
            ],
        },
    ]
    created = [request("/jobs", job) for job in jobs]
    print(f"Created candidate {candidate['id']} and jobs {[j['id'] for j in created]}.")
    print("Forward recommendations (fresh database: 100, 95.5, 90; Rust excluded):")
    print(json.dumps(request(f"/candidates/{candidate['id']}/recommendations?limit=10"), indent=2))
    print("Reverse recommendations:")
    print(json.dumps(request(f"/jobs/{created[0]['id']}/recommendations?limit=3"), indent=2))


if __name__ == "__main__":
    main()
