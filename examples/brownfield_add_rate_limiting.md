Add per-client rate limiting to the existing URL shortener API so that abusive
clients are throttled. Requests above the configured limit should receive an
HTTP 429 response. Apply it across all endpoints as middleware.
