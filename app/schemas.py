"""Validated public API contracts; camelCase matches the assignment."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

Text = Annotated[str, Field(min_length=1, max_length=200)]
NonNegative = Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False, strict=True)]
Years = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]


def normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateCreate(Contract):
    name: Text
    skills: Annotated[list[Text], Field(max_length=100)]
    yearsOfExperience: Years
    location: Text
    expectedSalary: NonNegative

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:
        return sorted({normalize(skill) for skill in value})


class Candidate(CandidateCreate):
    id: int


class RequiredSkill(Contract):
    name: Text
    importance: Literal["must-have", "nice-to-have"]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize(value)


class SalaryRange(Contract):
    min: NonNegative
    max: NonNegative

    @model_validator(mode="after")
    def ordered(self):
        if self.min > self.max:
            raise ValueError("salaryRange.min must be <= salaryRange.max")
        return self


class JobCreate(Contract):
    title: Text
    requiredSkills: Annotated[list[RequiredSkill], Field(max_length=100)]
    minYearsExperience: Years
    location: Text
    salaryRange: SalaryRange
    remoteAllowed: StrictBool

    @field_validator("requiredSkills")
    @classmethod
    def unique_skills(cls, value: list[RequiredSkill]) -> list[RequiredSkill]:
        names = [skill.name for skill in value]
        if len(names) != len(set(names)):
            raise ValueError("requiredSkills must have unique normalized names")
        return value


class Job(JobCreate):
    id: int


class Weights(Contract):
    skills: Annotated[int, Field(ge=0, le=100, strict=True)] = 50
    experience: Annotated[int, Field(ge=0, le=100, strict=True)] = 20
    location: Annotated[int, Field(ge=0, le=100, strict=True)] = 15
    salary: Annotated[int, Field(ge=0, le=100, strict=True)] = 15

    @model_validator(mode="after")
    def total_100(self):
        if sum((self.skills, self.experience, self.location, self.salary)) != 100:
            raise ValueError("weights must sum to 100")
        return self


class Contribution(Contract):
    score: float
    maxScore: int
    reason: str


class Breakdown(Contract):
    skills: Contribution
    experience: Contribution
    location: Contribution
    salary: Contribution


class Match(Contract):
    overallScore: float
    breakdown: Breakdown


class JobRecommendation(Match):
    job: Job


class CandidateRecommendation(Match):
    candidate: Candidate
