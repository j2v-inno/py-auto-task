# SQS Job Viewer

Small FastAPI app that polls an SQS queue, stores received job payloads in a local
SQLite DB, and exposes them over HTTP. Built for checking whether Orion automated-task
jobs arrive and what their payloads look like (see
`be/docs/infra/external-app-sqs-consumer.md`).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + current queue config |
| GET | `/received-jobs?limit=100&offset=0` | All stored jobs with parsed payloads |
| GET | `/get-job?id=1` or `?file_task_id=4917` | Single job |
| POST | `/poll-now?wait_time_seconds=0` | Manual trigger: one `receiveMessage` call, store + delete |

## Run with Docker

```bash
cd sqs-job-viewer
cp .env.example .env   # fill in SQS_QUEUE_URL, creds, endpoint
docker compose up --build
```

Then open http://localhost:3002/docs

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a   # or export vars manually on Windows
uvicorn app.main:app --reload --port 3002
```

## Notes

- A background thread long-polls SQS (`POLL_ENABLED=true` to disable use `false`
  and rely on `POST /poll-now`).
- Messages are stored first, then deleted when `DELETE_AFTER_STORE=true`.
  Set it to `false` if you want to inspect redeliveries.
- Duplicates by SQS `message_id` are acknowledged, not re-stored.
- For local testing against elasticmq, point `AWS_ENDPOINT_URL=http://localhost:9324`
  (or `http://elasticmq:9324` when on the same docker network).
