# Add paginated candidate and job listings

GET /candidates and GET /jobs return arrays in ascending ID order. Both accept limit (default 10, 1–100) and offset (default 0, nonnegative integer). Pagination happens in SQL. Empty or out-of-range pages return []. Offset pagination does not provide a snapshot across concurrent writes.
