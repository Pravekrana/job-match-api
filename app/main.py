"""HTTP orchestration: validate, persist, score, rank, limit."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import Base, CandidateRow, JobRow, make_engine
from app.schemas import (
    Candidate,
    CandidateCreate,
    CandidateRecommendation,
    Job,
    JobCreate,
    JobRecommendation,
    Weights,
)
from app.scoring import score_match


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


Db = Annotated[Session, Depends(get_session)]
Limit = Annotated[
    int, Query(ge=1, le=100, description="Top N results, after filtering and ranking")
]
ResourceId = Annotated[int, Path(gt=0)]
WeightParam = Annotated[int, Query(ge=0, le=100)]


def get_weights(
    skillsWeight: WeightParam = 50,
    experienceWeight: WeightParam = 20,
    locationWeight: WeightParam = 15,
    salaryWeight: WeightParam = 15,
) -> Weights:
    try:
        return Weights(
            skills=skillsWeight,
            experience=experienceWeight,
            location=locationWeight,
            salary=salaryWeight,
        )
    except ValidationError:
        raise HTTPException(422, "Weights must sum to 100") from None


WeightDependency = Annotated[Weights, Depends(get_weights)]


def get_or_404(session: Session, model, resource_id: int):
    record = session.get(model, resource_id)
    if record is None:
        label = "Candidate" if model is CandidateRow else "Job"
        raise HTTPException(404, f"{label} {resource_id} not found")
    return record


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(api: FastAPI):
        engine = make_engine(database_url or os.getenv("DATABASE_URL", "sqlite:///./job_match.db"))
        api.state.engine = engine
        try:
            Base.metadata.create_all(engine)
            yield
        finally:
            engine.dispose()

    api = FastAPI(
        title="Job Match API",
        version="1.0.0",
        lifespan=lifespan,
        description="Explainable recommendations. Must-have skills are always a hard filter.",
    )

    @api.get("/health", tags=["Operations"])
    def health(session: Db):
        session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @api.post("/candidates", response_model=Candidate, status_code=201, tags=["Candidates"])
    def create_candidate(payload: CandidateCreate, session: Db, response: Response):
        record = CandidateRow(**payload.model_dump())
        session.add(record)
        session.commit()
        session.refresh(record)
        response.headers["Location"] = f"/candidates/{record.id}"
        return Candidate.model_validate(record, from_attributes=True)

    @api.get("/candidates/{candidate_id}", response_model=Candidate, tags=["Candidates"])
    def get_candidate(candidate_id: ResourceId, session: Db):
        return Candidate.model_validate(
            get_or_404(session, CandidateRow, candidate_id), from_attributes=True
        )

    @api.post("/jobs", response_model=Job, status_code=201, tags=["Jobs"])
    def create_job(payload: JobCreate, session: Db, response: Response):
        record = JobRow(**payload.model_dump())
        session.add(record)
        session.commit()
        session.refresh(record)
        response.headers["Location"] = f"/jobs/{record.id}"
        return Job.model_validate(record, from_attributes=True)

    @api.get("/jobs/{job_id}", response_model=Job, tags=["Jobs"])
    def get_job(job_id: ResourceId, session: Db):
        return Job.model_validate(get_or_404(session, JobRow, job_id), from_attributes=True)

    @api.get(
        "/candidates/{candidate_id}/recommendations",
        response_model=list[JobRecommendation],
        tags=["Recommendations"],
    )
    def recommend_jobs(
        candidate_id: ResourceId,
        session: Db,
        weights: WeightDependency,
        limit: Limit = 10,
        minScore: float = Query(default=0, ge=0, le=100, allow_inf_nan=False),
    ):
        candidate = get_candidate(candidate_id, session)
        recommendations = []
        for row in session.scalars(select(JobRow)):
            job = Job.model_validate(row, from_attributes=True)
            match = score_match(candidate, job, weights)
            if match is not None and match.overallScore >= minScore:
                recommendations.append(JobRecommendation(job=job, **match.model_dump()))
        recommendations.sort(key=lambda item: (-item.overallScore, item.job.id))
        return recommendations[:limit]

    @api.get(
        "/jobs/{job_id}/recommendations",
        response_model=list[CandidateRecommendation],
        tags=["Recommendations"],
    )
    def recommend_candidates(
        job_id: ResourceId,
        session: Db,
        weights: WeightDependency,
        limit: Limit = 10,
        minScore: float = Query(default=0, ge=0, le=100, allow_inf_nan=False),
    ):
        job = get_job(job_id, session)
        recommendations = []
        for row in session.scalars(select(CandidateRow)):
            candidate = Candidate.model_validate(row, from_attributes=True)
            match = score_match(candidate, job, weights)
            if match is not None and match.overallScore >= minScore:
                recommendations.append(
                    CandidateRecommendation(candidate=candidate, **match.model_dump())
                )
        recommendations.sort(key=lambda item: (-item.overallScore, item.candidate.id))
        return recommendations[:limit]

    return api


app = create_app()
