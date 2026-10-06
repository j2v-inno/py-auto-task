import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from . import db, sqs_poller
from .config import settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    sqs_poller.start_poller()
    yield
    sqs_poller.stop_poller()


app = FastAPI(
    title="SQS Job Viewer",
    version="1.0.0",
    root_path=os.getenv("ROOT_PATH", ""),
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok", "queue_url": settings.sqs_queue_url, "poll_enabled": settings.poll_enabled}


@app.get("/received-jobs")
def received_jobs(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    jobs = db.list_jobs(limit, offset)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/get-job")
def get_job(id: int | None = None, file_task_id: int | None = None):
    if id is None and file_task_id is None:
        raise HTTPException(status_code=400, detail="Provide ?id= or ?file_task_id=")
    job = db.get_job(job_id=id, file_task_id=file_task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/poll-now")
def poll_now(wait_time_seconds: int = Query(0, ge=0, le=20)):
    """Manual trigger: fetch available messages from SQS once and store them."""
    try:
        messages = sqs_poller.fetch_once(wait_time_seconds=wait_time_seconds)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"fetched": len(messages), "messages": messages}
