from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.main import get_session


def test_readiness_failure_and_recovery(client):
    class BrokenSession:
        def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("private database credentials"))

    def broken_session():
        yield BrokenSession()

    client.app.dependency_overrides[get_session] = broken_session
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert client.get("/live").json() == {"status": "ok"}
    finally:
        client.app.dependency_overrides.clear()
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/live").status_code == 200


def test_readiness_openapi_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "503" in paths["/health"]["get"]["responses"]
    assert "/live" in paths


def test_real_session_connection_failure_and_recovery(client):
    engine = client.app.state.engine
    engine.dispose()

    def connection_failure(*args):
        raise OperationalError("connect", {}, Exception("private connection details"))

    event.listen(engine, "do_connect", connection_failure)
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert client.get("/live").status_code == 200
    finally:
        event.remove(engine, "do_connect", connection_failure)
    assert client.get("/health").json() == {"status": "ok"}
