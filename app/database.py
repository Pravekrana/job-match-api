"""Small relational persistence layer, portable between SQLite and PostgreSQL."""

from sqlalchemy import JSON, Boolean, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class CandidateRow(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    skills: Mapped[list[str]] = mapped_column(JSON)
    yearsOfExperience: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(200))
    expectedSalary: Mapped[float] = mapped_column(Float)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    requiredSkills: Mapped[list[dict]] = mapped_column(JSON)
    minYearsExperience: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(200))
    salaryRange: Mapped[dict] = mapped_column(JSON)
    remoteAllowed: Mapped[bool] = mapped_column(Boolean)


def make_engine(url: str):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
    return create_engine(url, **options)
