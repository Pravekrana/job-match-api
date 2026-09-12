import os

import pytest
from fastapi.testclient import TestClient

from app.database import Base, make_engine
from app.main import create_app


@pytest.fixture
def candidate_data():
    return {
        "name": "Asha Rao",
        "skills": ["Python", "SQL"],
        "yearsOfExperience": 3,
        "location": "Bengaluru",
        "expectedSalary": 100000,
    }


@pytest.fixture
def job_data():
    return {
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


@pytest.fixture
def client(tmp_path):
    # TEST_DATABASE_URL must reference a disposable database: its tables are reset per test.
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    if os.getenv("TEST_DATABASE_URL"):
        engine = make_engine(url)
        Base.metadata.drop_all(engine)
        engine.dispose()
    with TestClient(create_app(url)) as test_client:
        yield test_client
