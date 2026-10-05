# API retry policy

The payment client retries HTTP 503 at most twice with exponential backoff. A timeout after submission may hide a successful charge, so every retry reuses the same idempotency key. We review error rates weekly and stop retrying authentication failures. Retrying is different from restoring a saved database.
