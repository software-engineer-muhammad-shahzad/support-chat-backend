# Running locally

Two processes now, not one — document ingestion runs on a Celery worker,
not inline in the request. Without the worker running, an uploaded
document sits at `status: "processing"` forever.

```bash
# Terminal 1 — the Django app
python manage.py runserver

# Terminal 2 — the Celery worker (document ingestion: extract/chunk/embed)
python -m celery -A config worker --pool=threads --concurrency=4 --loglevel=info
```

`--pool=threads` (not the platform-default `prefork`) because:
- `prefork` doesn't work reliably on Windows.
- The task itself is I/O-bound (waiting on Supabase Storage and Gemini API
  calls, not CPU work), which is exactly what a thread pool is good at —
  `--concurrency=4` lets 4 documents ingest at once instead of queueing
  behind each other one at a time (`--pool=solo`, the common Windows
  fallback, always runs strictly one task at a time regardless of the
  concurrency number it reports at startup).

Broker is CloudAMQP (RabbitMQ) via `CELERY_BROKER_URL` in `.env`; task
results go to the same Redis used for the channel layer/presence
(`REDIS_URL`). See `config/celery.py` and the `CELERY_*` settings in
`config/settings.py`.
