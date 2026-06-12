# Distributed Background Job Scheduler — Architecture

## Overview
An async-first background job scheduler with a MinHeap priority queue, topological DAG dependency resolution, a starvation threshold engine, and a real-time SSE dashboard. Built with FastAPI, SQLAlchemy 2.0 async, asyncpg, and vanilla JavaScript.

---

## Phase 1: Core Scheduling (MinHeap + Timing Wheel)
- **MinHeap** (`app/scheduler/heap.py`): Balanced binary min-heap keyed on `(effective_priority, scheduled_at)`. Lower priority number = higher priority. Popped jobs are the most urgent.
- **Timing Wheel** (`app/scheduler/timing_wheel.py`): Coarse-grained time bucket for batching due jobs before heap insertion.
- **Staging Loader** (`app/scheduler/manager.py`): Polls DB for PENDING jobs with `scheduled_at <= now`, gates them through the DAG resolver, marks as PROCESSING, and pushes into the heap.

## Phase 2: Worker Execution Engine
- **WorkerEngine** (`app/worker/worker.py`): Continuous loop that pops from the heap and processes jobs. Supports concurrency via `asyncio.Semaphore`.
- **Exponential Backoff**: Failed jobs retry with `2^retry_count` delay (jittered). After 3 failures, routed to the Dead Letter Queue.
- **Email Handler** (`app/handlers/email_handler.py`): Simulated email processing with configurable failure rate.

## Phase 3: Dead Letter Queue
- **DLQ Table** (`app/models/dlq.py`): Stores permanently failed jobs with original ID, type, payload, error message, and failure timestamp.
- **Retry API** (`app/api/dlq.py`): `POST /api/dlq/{id}/retry` resurrects a DLQ entry back to the jobs table as PENDING.
- **Frontend Control Board**: DLQ table with per-row RETRY button, auto-refreshes every 5 seconds.

## Phase 4: Starvation Threshold Engine
- **Threshold**: 15 minutes (900 seconds). Jobs in PENDING state past this window are considered starved.
- **Daemon** (`app/worker/starvation.py`): Background task ticked every 60 seconds. Issues an atomic `UPDATE`:
  ```sql
  SET effective_priority = effective_priority - 1
  WHERE status = 'PENDING'
    AND scheduled_at <= NOW() - INTERVAL '15 minutes'
    AND effective_priority > 1
  ```
- **Design**: Only `effective_priority` is mutated; baseline `priority` remains immutable. The daemon is started as a background `asyncio.Task` inside `WorkerEngine.start()`.

## Phase 5: Topological DAG Resolver
- **Dependencies Column**: JSONB array of parent job UUIDs on the `jobs` table.
- **Gatekeeper** (`_is_topologically_ready` in `app/scheduler/manager.py` and `app/worker/worker.py`): Before a job enters the heap, all parent IDs are queried. If any parent has `status != 'completed'`, the job is skipped (remains PENDING) until its dependencies clear.
- **UUID Coercion**: Handles dependencies stored as strings, UUID objects, or JSON strings.

## Phase 6: Real-Time Oscilloscope Dashboard

### SSE Pipeline (`app/api/sse.py`)
- **Endpoint**: `GET /api/sse/stream`
- **Interval**: Every 2 seconds, queries `SELECT status, COUNT(*) FROM jobs GROUP BY status`
- **Format**: Server-Sent Events with `data: {json}\n\n` payload containing counts for PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED.
- **Transport**: Unbuffered `StreamingResponse` with `media_type="text/event-stream"`.

### Frontend (`frontend/`)
- **Stack**: Zero framework dependencies — vanilla HTML5, CSS3, JavaScript with Bootstrap 5.3.3 (CDN).
- **Data Flow**: Native `EventSource` API connects to `/api/sse/stream`. Auto-reconnects with 5s delay on error.
- **Time Zone**: All UTC database timestamps are localized to Lagos / West Africa Time (WAT, UTC+1) using `toLocaleString('en-NG', { timeZone: 'Africa/Lagos' })`.
- **Theme**: Light/dark mode toggle persisted to `localStorage`.

### DLQ Control Board
- Auto-fetches dead letter entries every 5 seconds via `GET /api/dlq`.
- Each row displays: failed_at (WAT), original_job_id, type, error_message, and a RETRY button.
- RETRY calls `POST /api/dlq/{id}/retry` to re-queue the job and refresh the table.

---

## API Routes Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sse/stream` | SSE stream of job status counts |
| GET | `/api/dlq` | List dead letter queue entries |
| POST | `/api/dlq/{id}/retry` | Re-queue a DLQ entry as pending |
| GET | `/api/jobs` | List all jobs |
| POST | `/api/jobs` | Create a new job |
| GET | `/api/jobs/pending/due` | Fetch due pending jobs |
| GET | `/api/jobs/{id}` | Get a single job |
| POST | `/api/jobs/{id}/cancel` | Cancel a pending job |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL DSN |
| `STARVATION_THRESHOLD_SECONDS` | 120 | Seconds before job considered starved |
| `STARVATION_CHECK_INTERVAL_SECONDS` | 30 | Daemon tick interval |
| `WORKER_POLL_INTERVAL` | 3.0 | Worker DB poll interval (seconds) |
| `MAX_RETRIES` | 3 | Max retry attempts before DLQ |
| `CONCURRENCY_LIMIT` | 10 | Max concurrent job executions |
