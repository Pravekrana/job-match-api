# Verification results

Verified on 2026-09-12 using Python 3.12.3 on Linux/WSL, with the dependencies
pinned in `requirements.txt` and `requirements-dev.txt`.

| Check | Result |
| --- | --- |
| `pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95` | **84 passed** in 11.20 seconds |
| Application coverage including branches | **98.82%** (99% rounded in the terminal) |
| Pure scorer coverage including branches | **100%** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 11 Python files |
| `python -m pip check` | No broken requirements |
| Compose and Actions YAML parsing | Passed; expected services and workflow steps checked |
| Live Uvicorn + `demo.py` | Passed as part of the suite over real localhost HTTP |

The live test uses a temporary SQLite database, creates the demonstration records,
checks the 100, 95.5 and 90 scores and exclusion of the Rust job, and exercises the
reverse endpoint. It stops its server afterward. The persistence test separately
checks records and recommendations after an application restart.

There are two dependency deprecation warnings from Starlette's test client:
its `httpx` compatibility path and an AnyIO `BlockingPortal` alias. Neither caused
a failure; they are left visible rather than suppressed.

Docker is not installed in this environment, and no PostgreSQL server is
available. **The container build and PostgreSQL execution have not been verified
locally.** The committed GitHub Actions workflow includes separate SQLite and
PostgreSQL test runs plus a Docker Compose build/start/demo smoke test. These
will run after the repository is pushed; no passing remote CI result is claimed.

The test client stalled under the execution environment's network sandbox.
The successful full suite ran with permission outside that sandbox, including
the live localhost HTTP test. No application workaround was needed.
