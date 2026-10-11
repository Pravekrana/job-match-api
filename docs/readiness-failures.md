# Return 503 on database readiness failure and expose liveness

GET /health checks database readiness: 200 when SELECT 1 succeeds, 503 with a generic Database unavailable detail on SQLAlchemy errors. GET /live returns 200 without database access so operators can distinguish process liveness from database readiness. Startup still requires the database to initialize successfully.
