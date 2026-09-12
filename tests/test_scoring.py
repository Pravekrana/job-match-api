import pytest
from pydantic import ValidationError

from app.schemas import CandidateCreate, JobCreate, Weights
from app.scoring import score_match


def score(candidate_data, job_data, weights=None):
    return score_match(CandidateCreate(**candidate_data), JobCreate(**job_data), weights)


def test_perfect_match(candidate_data, job_data):
    result = score(candidate_data, job_data)
    assert result.overallScore == 100
    assert [x[1].score for x in result.breakdown] == [50, 20, 15, 15]


@pytest.mark.parametrize("weights", [None, Weights(skills=0, experience=0, location=0, salary=100)])
def test_missing_one_must_have_always_excludes(candidate_data, job_data, weights):
    job_data["requiredSkills"].append({"name": "Rust", "importance": "must-have"})
    assert score(candidate_data, job_data, weights) is None


def test_optional_skills_boost_without_excluding(candidate_data, job_data):
    candidate_data["skills"] = ["Python"]
    without = score(candidate_data, job_data)
    assert without.breakdown.skills.score == 40
    candidate_data["skills"].append("SQL")
    assert score(candidate_data, job_data).overallScore == without.overallScore + 10


def test_partial_optional_coverage(candidate_data, job_data):
    job_data["requiredSkills"].append({"name": "Docker", "importance": "nice-to-have"})
    assert score(candidate_data, job_data).breakdown.skills.score == 45


def test_normalization_and_duplicate_candidate_skills(candidate_data, job_data):
    candidate_data["skills"] = [" PYTHON ", "python", " Sql "]
    candidate_data["location"] = "  BENGALURU  "
    assert CandidateCreate(**candidate_data).skills == ["python", "sql"]
    assert score(candidate_data, job_data).overallScore == 100


@pytest.mark.parametrize("requirements", [[], [{"name": "python", "importance": "must-have"}]])
def test_no_optional_skills_earns_full_skill_score(candidate_data, job_data, requirements):
    job_data["requiredSkills"] = requirements
    assert score(candidate_data, job_data).breakdown.skills.score == 50


def test_empty_candidate_skills_allowed_for_jobs_without_requirements(candidate_data, job_data):
    candidate_data["skills"] = []
    job_data["requiredSkills"] = []
    assert score(candidate_data, job_data).overallScore == 100


@pytest.mark.parametrize(
    "years,minimum,expected", [(0, 3, 0), (1.5, 3, 10), (3, 3, 20), (30, 3, 20), (0, 0, 20)]
)
def test_experience_penalized_proportionally(candidate_data, job_data, years, minimum, expected):
    candidate_data["yearsOfExperience"] = years
    job_data["minYearsExperience"] = minimum
    result = score(candidate_data, job_data)
    assert result is not None
    assert result.breakdown.experience.score == expected


def test_location_order(candidate_data, job_data):
    exact = score(candidate_data, job_data).breakdown.location.score
    job_data["location"] = "Delhi"
    job_data["remoteAllowed"] = True
    remote = score(candidate_data, job_data).breakdown.location.score
    job_data["remoteAllowed"] = False
    mismatch = score(candidate_data, job_data).breakdown.location.score
    assert (exact, remote, mismatch) == (15, 10.5, 0)


@pytest.mark.parametrize(
    "expectation,low,high,points",
    [
        (100, 0, 99, 0),
        (100, 50, 100, 7.5),
        (100, 50, 150, 11.25),
        (100, 100, 150, 15),
        (100, 120, 150, 15),
        (100, 100, 100, 15),
        (100, 90, 90, 0),
        (0, 0, 0, 15),
        (0, 0, 100, 15),
        (100, 0, 0, 0),
    ],
)
def test_salary_boundaries(candidate_data, job_data, expectation, low, high, points):
    candidate_data["expectedSalary"] = expectation
    job_data["salaryRange"] = {"min": low, "max": high}
    assert score(candidate_data, job_data).breakdown.salary.score == points


def test_custom_weights(candidate_data, job_data):
    candidate_data["skills"] = ["Python"]
    result = score(
        candidate_data, job_data, Weights(skills=100, experience=0, location=0, salary=0)
    )
    assert result.overallScore == 80
    assert result.breakdown.skills.maxScore == 100
    assert result.breakdown.salary.maxScore == 0


@pytest.mark.parametrize(
    "weights", [{"skills": 51}, {"skills": -1}, {"skills": 50.5}, {"skills": True}, {"skills": 101}]
)
def test_invalid_weights_rejected(weights):
    with pytest.raises(ValidationError):
        Weights(**weights)


def test_scores_bounded_and_displayed_breakdown_sums(candidate_data, job_data):
    for years in [0, 1, 2, 3, 10]:
        for salary in [0, 99999, 100000, 120000, 140000, 140001]:
            candidate_data.update(yearsOfExperience=years, expectedSalary=salary)
            result = score(candidate_data, job_data)
            assert 0 <= result.overallScore <= 100
            assert result.overallScore == round(sum(c.score for _, c in result.breakdown), 2)
            assert all(0 <= c.score <= c.maxScore for _, c in result.breakdown)


def test_more_experience_and_skills_never_reduce_score(candidate_data, job_data):
    previous = -1
    for years in [0, 1, 2, 3, 10]:
        candidate_data["yearsOfExperience"] = years
        current = score(candidate_data, job_data).overallScore
        assert current >= previous
        previous = current


def test_higher_salary_range_never_reduces_score(candidate_data, job_data):
    previous = -1
    for low, high in [(0, 50000), (50000, 100000), (75000, 125000), (100000, 150000)]:
        job_data["salaryRange"] = {"min": low, "max": high}
        current = score(candidate_data, job_data).overallScore
        assert current >= previous
        previous = current
