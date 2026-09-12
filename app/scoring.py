"""Pure scorer shared by forward and reverse recommendations. No database or HTTP."""

from app.schemas import (
    Breakdown,
    CandidateCreate,
    Contribution,
    JobCreate,
    Match,
    Weights,
    normalize,
)


def score_match(
    candidate: CandidateCreate, job: JobCreate, weights: Weights | None = None
) -> Match | None:
    weights = weights or Weights()
    available = {normalize(skill) for skill in candidate.skills}
    must = {skill.name for skill in job.requiredSkills if skill.importance == "must-have"}
    nice = {skill.name for skill in job.requiredSkills if skill.importance == "nice-to-have"}
    if not must.issubset(available):
        return None

    # Must-have eligibility earns 80%; optional coverage earns the remaining 20%.
    # With no optional requirements there is no missing evidence to penalize.
    matched = len(nice & available)
    skill_factor = 0.8 + 0.2 * matched / len(nice) if nice else 1.0
    experience_factor = (
        min(candidate.yearsOfExperience / job.minYearsExperience, 1.0)
        if job.minYearsExperience
        else 1.0
    )
    if normalize(candidate.location) == normalize(job.location):
        location_factor, location_reason = 1.0, "Exact normalized location match"
    elif job.remoteAllowed:
        location_factor, location_reason = 0.7, "Different location; remote work allowed"
    else:
        location_factor, location_reason = 0.0, "Different location; remote work unavailable"

    expected, low, high = candidate.expectedSalary, job.salaryRange.min, job.salaryRange.max
    if high < expected:
        salary_factor, salary_reason = 0.0, "Maximum salary is below expectation"
    elif expected <= low:
        salary_factor, salary_reason = 1.0, "Entire salary range meets or exceeds expectation"
    else:
        # Here high >= expected > low, so the denominator is strictly positive.
        overlap = (high - expected) / (high - low)
        salary_factor = 0.5 + 0.5 * overlap
        salary_reason = f"Expectation within range; {overlap:.0%} of range meets expectation"

    def contribution(factor: float, maximum: int, reason: str) -> Contribution:
        return Contribution(score=round(factor * maximum, 2), maxScore=maximum, reason=reason)

    breakdown = Breakdown(
        skills=contribution(
            skill_factor,
            weights.skills,
            f"All {len(must)} must-have skills met; {matched}/{len(nice)} nice-to-have skills met",
        ),
        experience=contribution(
            experience_factor,
            weights.experience,
            f"{candidate.yearsOfExperience:g} years against {job.minYearsExperience:g} minimum; "
            + ("minimum met" if experience_factor == 1 else "proportional shortfall penalty"),
        ),
        location=contribution(location_factor, weights.location, location_reason),
        salary=contribution(salary_factor, weights.salary, salary_reason),
    )
    # Sum displayed contributions so the response always adds up for the reviewer.
    total = round(sum(getattr(breakdown, key).score for key in Weights.model_fields), 2)
    return Match(overallScore=total, breakdown=breakdown)
