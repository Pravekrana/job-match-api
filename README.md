# Job Match API

A small, explainable job recommendation service built with Python 3.12, FastAPI,
Pydantic and SQLAlchemy. SQLite makes local setup simple; Docker Compose runs the
same API against PostgreSQL. Includes forward and reverse recommendations,
per-request weights, persistent storage, OpenAPI documentation and focused tests.

## Run locally

Run these commands from the repository root. Python 3.12 is the tested version.

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Linux / macOS / WSL:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive API documentation.
The database is created automatically as `job_match.db` in the working directory
and persists across restarts. No database setup or environment file is needed.
`DATABASE_URL` overrides the default, e.g.
`postgresql+psycopg://user:password@localhost:5432/jobmatch`.

In a second terminal, run the demo to create one candidate and four jobs and print
both recommendation views:

```bash
python demo.py
```

The demo uses only Python's standard library. On Windows, `py -3.12 demo.py` also
works. On Linux, use `python3 demo.py` if `python` is unavailable. Each run creates
new records; it does not clear existing data. In an initially empty database, the
recommended scores are **100, 95.5, 90**, with the Rust job excluded.

## Run with Docker and PostgreSQL

Requires Docker Engine/Desktop with Compose v2.

```bash
docker compose up --build -d
docker compose ps
docker compose logs api
```

Use the same `/docs` URL and demo command. Compose waits for PostgreSQL's health
check before starting the API; the API health check also queries the database.
PostgreSQL data lives in a named volume. The API runs as a non-root user and is
bound to localhost; the database port is not published. The included database
credentials are local development defaults.

```bash
docker compose down
```

This stops the stack while keeping the data. `docker compose down -v` **deletes
the database volume** if you deliberately want a fresh demo database.

## API contract

| Method | Endpoint | Result |
| --- | --- | --- |
| POST | `/candidates` | Create a candidate; 201 with generated ID and Location header |
| GET | `/candidates/{id}` | Read the stored profile |
| POST | `/jobs` | Create a job; 201 with generated ID and Location header |
| GET | `/jobs/{id}` | Read the stored posting |
| GET | `/candidates/{id}/recommendations?limit=10` | Ranked jobs for a candidate |
| GET | `/jobs/{id}/recommendations?limit=10` | Ranked candidates for a job |
| GET | `/health` | Database readiness check |

IDs are server-generated positive integers. Missing records return **404**.
Invalid bodies, IDs, limits or weights return **422** with a `detail` field.
An existing record with no eligible matches returns **200** and `[]`.
`limit` defaults to 10 and accepts integers from 1 to 100. Filtering and ranking
happen **before** applying the limit. Ties use ascending ID for repeatable results.

Candidate request:

```json
{
  "name": "Asha Rao",
  "skills": ["Python", "SQL"],
  "yearsOfExperience": 3,
  "location": "Bengaluru",
  "expectedSalary": 100000
}
```

Job request:

```json
{
  "title": "Backend Engineer",
  "requiredSkills": [
    {"name": "Python", "importance": "must-have"},
    {"name": "SQL", "importance": "nice-to-have"}
  ],
  "minYearsExperience": 3,
  "location": "Bengaluru",
  "salaryRange": {"min": 100000, "max": 140000},
  "remoteAllowed": false
}
```

Use **Try it out** in `/docs` to submit these bodies. Recommendations return a JSON
array; each item contains the complete `job` (or `candidate` in the reverse view),
`overallScore`, and this breakdown shape:

```json
{
  "skills": {"score": 50, "maxScore": 50, "reason": "All 1 must-have skills met; 1/1 nice-to-have skills met"},
  "experience": {"score": 20, "maxScore": 20, "reason": "3 years against 3 minimum; minimum met"},
  "location": {"score": 15, "maxScore": 15, "reason": "Exact normalized location match"},
  "salary": {"score": 15, "maxScore": 15, "reason": "Entire salary range meets or exceeds expectation"}
}
```

## Scoring formula and design reasoning

The score is a **fit heuristic, not a hiring probability**. It uses only the four
requested dimensions. Names and IDs never contribute to the score.

### 1. Eligibility comes first

Every must-have skill must be present in the candidate's skills. Otherwise, the
pair is excluded before any weighted scoring. Setting `skillsWeight=0` cannot
bypass this rule. Both recommendation directions call the same pure function.

Skills and locations are compared after trimming/collapsing whitespace and
Unicode case folding. `Python` and ` python ` match; `JS` and `JavaScript` do not.
Candidate skill duplicates are removed. Duplicate normalized job skill names are
rejected, including conflicting must-have/nice-to-have declarations.

### 2. Compute factors between 0 and 1

| Dimension | Default maximum | Factor |
| --- | ---: | --- |
| Skills | 50 | If nice-to-haves exist: `0.8 + 0.2 × matchedNice / totalNice`; otherwise `1` |
| Experience | 20 | `min(candidateYears / minimumYears, 1)`; `1` if minimum is zero |
| Location | 15 | Exact normalized match: `1`; otherwise remote allowed: `0.7`; otherwise `0` |
| Salary | 15 | Piecewise salary feasibility and range coverage, described below |

**Why these weights?** Skills are central to doing the work, so they carry half
the score. The mandatory subset establishes eligibility and earns 80% of the
skill budget (40 of 50 by default); optional coverage contributes up to 10 extra
points. This makes optional skills useful without letting a long wish list
dominate. With no nice-to-haves, an eligible candidate receives all 50 points.
With no required skills at all, skills are unconstrained and also earn full
points. This deliberately avoids penalizing applicants for absent requirements;
it can favor sparse postings, a limitation worth revisiting with product input.

Experience gets 20 points because it is relevant but an imperfect proxy for
ability. **Penalizing rather than excluding** allows a candidate with strong
skills and slightly fewer years to remain visible. Three years against a
six-year minimum earns 10/20, not a rejection. Extra experience is capped rather
than automatically favored, and fractional years are supported.

Location and salary each get 15 points because they affect practical acceptance
without replacing skill suitability. Exact location scores 15, remote scores
10.5, and a mismatch scores zero. Exact matches win even if the job also permits
remote work. Remote is treated as feasible with some coordination friction, in
accordance with the assignment's required ordering; the data does not include a
candidate's actual remote-work preference.

### Salary: interpreting a point expectation against a range

Assume salaries are annual amounts in the same currency and `expectedSalary` is
the candidate's minimum acceptable amount. Since it is a point, interval-to-
interval overlap is undefined. Instead, measure feasibility plus the share of
the advertised range that meets the expectation.

Let `E = expectedSalary`, `L = range.min`, and `H = range.max`:

```text
if H < E:       factor = 0
else if E <= L: factor = 1
else:          factor = 0.5 + 0.5 × (H - E) / (H - L)
```

The last branch always has `H > L`, so fixed salary ranges never divide by zero.
An unaffordable role gets **0/15**, but remains eligible if the skills match.
When only the maximum meets expectation, salary earns **7.5/15** for feasibility.
When the entire range meets or exceeds expectation, it earns **15/15**; a job
comfortably above expectation therefore receives the highest score.

For `E = 100,000`:

| Range | Salary points | Interpretation |
| --- | ---: | --- |
| 70,000–99,999 | 0 | Cannot meet expectation |
| 70,000–100,000 | 7.5 | Meets expectation only at the ceiling |
| 80,000–120,000 | 11.25 | Half the range is acceptable |
| 100,000–140,000 | 15 | Entire range acceptable |
| 120,000–160,000 | 15 | Comfortably affordable, capped at full credit |
| 100,000–100,000 | 15 | A fixed offer that meets expectation |

The jump at `H = E` is intentional: feasible and infeasible offers are different.
Full credit for a fixed offer at expectation follows the entire-range rule.
The range-coverage term is not a probability of receiving a particular offer.
No additional reward above full coverage avoids letting unusually high salaries
overwhelm relevance. Zero expectation is allowed and earns full salary credit
for any valid nonnegative range.

### 3. Combine and rank

Each contribution is `round(weight × factor, 2)`. `overallScore` is the sum of
these displayed contributions, rounded to two decimals, bounded to 0–100 by
construction. Ranking uses that displayed score, then ascending ID for ties.

Worked example: an eligible candidate with half the nice-to-haves, three of six
required years, a remote location fit, and expectation 100,000 against an
80,000–120,000 range gets **45 + 10 + 10.5 + 11.25 = 76.75**.

### Configurable weights

Both recommendation endpoints accept these optional query parameters:

```text
?skillsWeight=40&experienceWeight=20&locationWeight=10&salaryWeight=30&limit=5
```

Weights must be integers between 0 and 100 and sum to **100**. Omitted values
keep their defaults, so update all affected weights together. Explicit totals
are easier to explain than silently normalizing arbitrary inputs. Configuration
applies only to that request; it does not mutate global state. The pure scorer
also accepts a validated `Weights` object.

## Tests and quality checks

After installing `requirements-dev.txt`:

```bash
python -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95
python -m ruff check .
python -m ruff format --check .
```

Use `.venv/bin/python` on Linux/WSL or `.\.venv\Scripts\python.exe` on Windows if
the virtual environment is not activated.

Tests cover hard exclusion (including zero skill weight), optional coverage,
normalization, zero/fractional/excess experience, location ordering, unaffordable
and fixed salary ranges, zero expectation, custom weights, score bounds and
rounding, ranking, ties, top-N, reverse consistency, validation, missing records,
empty results, and persistence across application restarts.

The GitHub Actions workflow runs the suite against SQLite and PostgreSQL 16,
and separately builds and starts Docker Compose to run the live demo.
To run against PostgreSQL yourself, create a **disposable test database**, set
`TEST_DATABASE_URL` to its SQLAlchemy connection URL, then run pytest.
**The test fixture drops and recreates the application's tables in that database.**
It never uses `DATABASE_URL` as its test database.

Local verification results and environment limitations are recorded in
[TEST_RESULTS.md](TEST_RESULTS.md).

## Structure and scope

```text
app/schemas.py     Request validation and response contracts
app/scoring.py     Pure scoring policy; no HTTP or database dependencies
app/database.py    SQLAlchemy tables and engine setup
app/main.py        HTTP routes, persistence and ranking
tests/            Scoring and API tests
demo.py           Live HTTP demonstration using standard Python
```

Assumptions and tradeoffs:

- One currency and annual salary basis across all records; no conversion.
- Skill synonyms, geographic aliases, relocation and remote eligibility by
  country are not inferred. No fuzzy matching is hidden in the score.
- Inputs use JSON numbers (not numeric strings or booleans) for years/salary;
  years must be 0–100 and salaries 0–1 trillion. Text must be nonblank and at most
  200 characters, with at most 100 skills. Unknown fields are rejected.
- JSON columns keep skill lists and salary ranges compact across both databases.
  Validation occurs at the API boundary; direct database writes are unsupported.
  Floating point values are sufficient for this heuristic; use fixed precision
  amounts for monetary transactions or strict currency precision requirements.
- The API scans available records and sorts eligible matches: roughly
  `O(J × S + J log J)` for J jobs and S skills, with O(J) result memory. Reverse
  matching scales with candidates instead. `limit` limits output, not computation.
- Startup creates tables for this small assignment. It does not migrate existing
  schemas. Run a single API process for the demo.
- No authentication, frontend, machine learning, update/delete routes, or
  collaborative filtering, as these are outside the requested scope.

With more time: add migrations and database constraints, normalize/index skills
for database-side eligibility filtering, use bounded top-N selection and
pagination, add structured operational logs, and validate the policy with
recruiters and candidates using labeled examples. Explicit currency and remote
preferences would improve the model. Policy versioning would preserve explanations
when weights or formulas evolve.

## AI tool disclosure

This implementation was produced with substantial assistance from OpenAI Codex:
code, tests, documentation, and local verification were AI-assisted. It should
not be represented as entirely unaided work. The commit history records actual
implementation stages and uses Codex attribution for those commits.

During implementation, the AI-generated draft was refined to use a normal
FastAPI `Path` import instead of a dynamic import, make the Docker working
directory writable by its non-root user, and apply consistent formatting.
Salary boundary choices, immutable per-request weights, and regression tests
were made explicit in the implementation. These are AI-assisted revisions,
not claims of independent human overrides.

The submitter should review the scorer and tests, run the project, and add any
actual personal changes or disagreements here before submitting. No human-only
modifications or review are claimed by this document.

## Publish to GitHub

The supplied folder is already a Git repository with incremental commits.
Create an **empty** repository named `job-match-api` in your GitHub account;
do not initialize it with another README, license, or `.gitignore`.

From this project directory:

```bash
git config user.name "YOUR NAME"
git config user.email "YOUR GITHUB EMAIL"
git remote add origin https://github.com/YOUR_USERNAME/job-match-api.git
git push -u origin main
```

Use your GitHub login through Git Credential Manager when prompted. The local
identity configuration applies to your future commits; it does not rewrite the
existing AI-assisted history. After your review or changes, commit those normally:

```bash
git add .
git commit -m "docs: record my review and scoring decisions"
git push
```

Only create that review commit after actually reviewing or changing the files.
Check the Actions tab after pushing. Submit the repository URL, ensuring the
reviewer has access. A GitHub URL cannot be supplied until you publish the repo
under your account. Never add the virtual environment, local database or secrets.

## Reference

Persistence follows SQLAlchemy's documented declarative mapping and session
patterns: [SQLAlchemy ORM quick start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html).
