# Background Job Scheduler

**HNG Stage 9** — Dilamme Engineering Task

Heap-based distributed background job scheduler with DAG dependency resolution, starvation prevention, real-time SSE dashboard, and dead-letter queue.

---

## Quick Start (Development)

```bash
# 1. Start PostgreSQL
docker compose up db -d

# 2. Copy env vars
cp .env.example .env
# Edit .env with your DATABASE_URL

# 3. Run the API server
uv run uvicorn app.main:app --reload --port 8000

# 4. In another terminal, run the worker
uv run python run_worker.py
```

- **Dashboard:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

---

## Production Deployment

### Prerequisites

- Ubuntu 24.04 / Debian 12 server with Docker
- A public domain (e.g. via [DuckDNS](https://duckdns.org))
- Ports 80 and 443 open

### Automatic deploy

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USER/background_job_scheduler/main/scripts/deploy.sh \
  | bash /dev/stdin your-domain.duckdns.org admin@example.com
```

### Manual deploy

```bash
git clone https://github.com/YOUR_USER/background_job_scheduler.git /opt/scheduler
cd /opt/scheduler
cp .env.example .env          # edit DATABASE_URL, EMAIL_FAILURE_RATE, etc.
docker compose up --build -d
```

### Nginx + SSL

```bash
sudo cp nginx/nginx.conf /etc/nginx/sites-available/scheduler
# Edit domain name in the config, then:
sudo ln -sf /etc/nginx/sites-available/scheduler /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx --agree-tos --email admin@example.com --domains your-domain.duckdns.org
```

### Docker services

| Service  | Image          | Command                     |
|----------|----------------|-----------------------------|
| `db`     | postgres:16    | —                           |
| `api`    | custom build   | `uvicorn app.main:app ...`  |
| `worker` | custom build   | `python run_worker.py`      |

```bash
docker compose logs -f api      # tail API logs
docker compose logs -f worker   # tail worker logs
```

---

## API Reference

Base URL: `http://127.0.0.1:8000/api` (dev) / `https://your-domain.duckdns.org/api` (prod)

Interactive docs: `https://your-domain.duckdns.org/docs`

---

### 1. Create a Job

`POST /api/jobs`

Creates a new job and returns the full job object with an auto-generated UUID.

**Request body**

| Field          | Type            | Default  | Constraints            | Description                                    |
|----------------|-----------------|----------|------------------------|------------------------------------------------|
| `type`         | `string`        | —        | required               | Job type identifier (e.g. `"email"`)            |
| `payload`      | `object`        | —        | required, JSON         | Arbitrary job payload                          |
| `priority`     | `integer`       | `3`      | 1–3                    | 1 = Highest, 2 = Medium, 3 = Low               |
| `scheduled_at` | `string` (ISO)  | —        | required, datetime     | When the job should first run                  |
| `interval`     | `integer`\|null | `null`   | seconds                | Repeat interval; omit/null = one-off           |
| `dependencies` | `[string]`      | `[]`     | UUIDs                  | Jobs that must complete before this one runs   |

Extra fields not listed above → **422**.

**Response: `201 Created`**

```json
{
  "id": "0194f2a1-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "type": "email",
  "status": "pending",
  "payload": {"to": "user@example.com", "subject": "Welcome"},
  "priority": 2,
  "effective_priority": 2,
  "scheduled_at": "2026-06-12T14:30:00+00:00",
  "created_at": "2026-06-12T12:00:00+00:00",
  "retry_count": 0,
  "interval": null,
  "dependencies": []
}
```

**Errors:** `422` — missing/invalid fields, out-of-range priority, extra fields.

---

### 2. List All Jobs

`GET /api/jobs`

Returns all jobs ordered by `created_at` descending (newest first).

**Response: `200 OK`**

```json
[
  {
    "id": "0194f2a1-...",
    "type": "email",
    "status": "pending",
    "payload": {"to": "user@example.com"},
    "priority": 3,
    "effective_priority": 3,
    "scheduled_at": "2026-06-12T14:30:00+00:00",
    "created_at": "2026-06-12T12:00:00+00:00",
    "retry_count": 0,
    "interval": null,
    "dependencies": []
  }
]
```

**Errors:** None (always returns array, possibly empty).

---

### 3. Get Pending Due Jobs

`GET /api/jobs/pending/due`

Returns jobs where `status == "pending"` and `scheduled_at` is in the past. Limited to 50 results.

**Response: `200 OK`** — array of job objects (same schema as list).

---

### 4. Get Job by ID

`GET /api/jobs/{job_id}`

**Path params**

| Param    | Type   | Description          |
|----------|--------|----------------------|
| `job_id` | `UUID` | The job's unique ID |

**Response: `200 OK`** — single job object.

**Errors:** `404` — job not found. `422` — invalid UUID.

---

### 5. Cancel a Job

`POST /api/jobs/{job_id}/cancel`

Cancels a job. Works on `PENDING`, `PROCESSING`, `FAILED`, and already `CANCELLED` jobs. **Does not** work on `COMPLETED` jobs.

**Path params**

| Param    | Type   | Description                  |
|----------|--------|------------------------------|
| `job_id` | `UUID` | The job to cancel            |

**Request body:** none (empty).

**Response: `200 OK`** — the updated job with `status: "cancelled"`.

**Errors:** `404` — not found. `409` — job is completed. `422` — invalid UUID.

---

### 6. List Dead-Letter Queue

`GET /api/dlq`

Returns all DLQ entries ordered by `failed_at` descending.

**Response: `200 OK`**

```json
[
  {
    "id": "0194f2b2-...",
    "original_job_id": "0194f2a1-...",
    "type": "email",
    "payload": {"to": "user@example.com"},
    "failed_at": "2026-06-12T12:05:00+00:00",
    "error_message": "Server Timeout: Failed to reach recipient server for user@example.com"
  }
]
```

| Field            | Type            | Description                          |
|------------------|-----------------|--------------------------------------|
| `id`             | `UUID`          | DLQ entry ID                         |
| `original_job_id`| `UUID`          | Original failed job's ID             |
| `type`           | `string`        | Job type                             |
| `payload`        | `object`        | Original job payload                 |
| `failed_at`      | `string` (ISO)  | When the job permanently failed      |
| `error_message`  | `string`\|null  | Last error message                   |

---

### 7. Retry a Dead-Letter

`POST /api/dlq/{dlq_id}/retry`

Resurrects a DLQ entry as a brand new `PENDING` job with a fresh UUID, reset retry count, and immediate scheduling.

**Path params**

| Param    | Type   | Description               |
|----------|--------|---------------------------|
| `dlq_id` | `UUID` | The DLQ entry to retry    |

**Request body:** none (empty).

**Response: `200 OK`**

```json
{
  "message": "Job resurrected from DLQ. New job ID: 0194f2c3-..."
}
```

**Errors:** `404` — DLQ entry not found. `422` — invalid UUID.

---

### 8. SSE Metrics Stream

`GET /api/sse/stream`

**Response type:** `text/event-stream`

An infinite stream that pushes job status counts every 2 seconds.

```text
data: {"PENDING": 15, "PROCESSING": 3, "COMPLETED": 120, "FAILED": 2, "CANCELLED": 5}

```

| Field        | Type   | Description                       |
|--------------|--------|-----------------------------------|
| `PENDING`    | `int`  | Count of pending jobs             |
| `PROCESSING` | `int`  | Count of processing jobs          |
| `COMPLETED`  | `int`  | Count of completed jobs           |
| `FAILED`     | `int`  | Count of failed jobs              |
| `CANCELLED`  | `int`  | Count of cancelled jobs           |

On error: `data: {"error": "<message>"}\n\n`

---

### Response Fields Reference

**Job object** (returned by all `/jobs` endpoints)

| Field              | Type            | Description                                     |
|--------------------|-----------------|-------------------------------------------------|
| `id`               | `UUID`          | Auto-generated job ID (uuid7)                    |
| `type`             | `string`        | Job type identifier                             |
| `status`           | `enum`          | `pending` / `processing` / `completed` / `failed` / `cancelled` |
| `payload`          | `object`        | Arbitrary JSON payload                          |
| `priority`         | `integer` (1–3) | Original priority                                |
| `effective_priority`| `integer`       | Current effective priority (may be boosted by starvation daemon) |
| `scheduled_at`     | `string` (ISO)  | Scheduled execution time                        |
| `created_at`       | `string` (ISO)  | Creation timestamp                              |
| `retry_count`      | `integer`       | Number of retries attempted (max 3)             |
| `interval`         | `integer`\|null | Repeat interval in seconds, or null             |
| `dependencies`     | `[string]`      | UUIDs of prerequisite jobs                      |

---

### Status Code Summary

| Code | Meaning                       | Endpoints                                         |
|------|-------------------------------|---------------------------------------------------|
| 200  | Success                       | All GET, POST cancel, POST retry, SSE stream      |
| 201  | Created                       | `POST /jobs`                                      |
| 404  | Not found                     | `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `POST /dlq/{id}/retry` |
| 409  | Conflict                      | `POST /jobs/{id}/cancel` (job completed)          |
| 422  | Validation error              | All endpoints with request body or path params    |

---

## Job Status Flow

```
                  ┌──────────┐
                  │ PENDING  │
                  └────┬─────┘
                       │ worker picks up
                       ▼
                  ┌──────────┐
         ┌───────│PROCESSING│───────┐
         │       └──────────┘       │
         ▼                          ▼
    ┌──────────┐              ┌──────────┐
    │ COMPLETED│              │  FAILED  │
    └──────────┘              └────┬─────┘
                                   │ retries exhausted
                                   ▼
                              ┌──────────┐
                              │   DLQ    │
                              └──────────┘
                                   │ manual retry
                                   ▼
                              ┌──────────┐
                              │ PENDING  │  (new job)
                              └──────────┘

Cancellation: any status → CANCELLED (except COMPLETED)
```

---

## Configuration

| Variable                        | Default                                          | Description                     |
|---------------------------------|--------------------------------------------------|---------------------------------|
| `DATABASE_URL`                  | `postgresql+asyncpg://postgres:password@localhost:5432/scheduler_db` | Database connection string |
| `EMAIL_FAILURE_RATE`            | `0.0`                                            | Probability of email failure    |
| `MAX_RETRIES`                   | `3`                                              | Max retry attempts              |
| `WORKER_POLL_INTERVAL`          | `3.0`                                            | Worker DB poll interval (s)     |
| `CONCURRENCY_LIMIT`             | `10`                                             | Max concurrent jobs             |
| `STARVATION_THRESHOLD_SECONDS`  | `900`                                            | Time before priority boost (s)  |
| `STARVATION_CHECK_INTERVAL_SECONDS` | `60`                                         | Starvation daemon tick (s)      |
| `DLQ_ALERT_THRESHOLD`           | `10`                                             | DLQ count before email alert    |
| `ALERT_EMAIL`                   | `admin@dilamme.com`                              | Alert recipient                 |

---

## Architecture

See [`architecture.md`](architecture.md) for the full architecture document covering:

1. Core Models & DB Schema
2. REST API Layer
3. MinHeap Priority Queue
4. Worker Engine + Retry + DLQ
5. Starvation Engine + DAG Resolver
6. Oscilloscope Dashboard (SSE)

---

## Benchmark

```bash
uv run python -m app.scheduler.benchmark
```

Compares Min-Heap (O(log n)) vs Timing Wheel (O(1)) insert/extract with 10 000 jobs.

```
[Min-Heap - O(log n)]
  Insert:  0.03876 seconds
  Extract: 0.32207 seconds

[Timing Wheel - O(1)]
  Insert:  0.00208 seconds
  Extract: 0.00015 seconds
```

The Timing Wheel is **~18× faster on insert** and **~2147× faster on extract** for 10 000 jobs. This is expected: the heap's O(log n) extract requires bubbling down the tree, while the Timing Wheel simply checks the next slot. Trade-off: the Timing Wheel uses more memory (fixed array of slots) and works best when job delays fall within a bounded range.
