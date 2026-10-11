# Filter recommendations by a validated minimum score

Both recommendation endpoints accept minScore, a finite number from 0 through 100 (default 0). Eligible pairs must have an overallScore greater than or equal to minScore after applying request weights. Filtering precedes ranking and limit. The must-have skill filter remains mandatory.
