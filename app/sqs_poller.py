import logging
import threading
import time

import boto3

from . import db
from .config import settings

log = logging.getLogger("sqs_job_viewer.sqs")

_client = None
_client_lock = threading.Lock()
_stop = threading.Event()


def get_client():
    global _client
    with _client_lock:
        if _client is None:
            _client = boto3.client(
                "sqs",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                endpoint_url=settings.aws_endpoint_url,
            )
    return _client


def fetch_once(wait_time_seconds: int | None = None) -> list[dict]:
    """One receiveMessage call. Stores messages locally, optionally deletes from SQS."""
    if not settings.sqs_queue_url:
        raise RuntimeError("SQS_QUEUE_URL is not configured")

    resp = get_client().receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=settings.max_messages,
        WaitTimeSeconds=settings.wait_time_seconds if wait_time_seconds is None else wait_time_seconds,
        VisibilityTimeout=settings.visibility_timeout,
        AttributeNames=["All"],
    )
    stored = []
    for msg in resp.get("Messages", []):
        row_id = db.store_job(msg, settings.sqs_queue_url)
        if row_id is None:
            log.info("Duplicate message %s, acking", msg.get("MessageId"))
        if settings.delete_after_store:
            get_client().delete_message(
                QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"]
            )
            db.mark_deleted(msg["MessageId"])
        stored.append(
            {
                "id": row_id,
                "message_id": msg.get("MessageId"),
                "duplicate": row_id is None,
                "body": msg.get("Body"),
            }
        )
    return stored


def poll_loop() -> None:
    log.info("Poller started for %s", settings.sqs_queue_url)
    while not _stop.is_set():
        try:
            found = fetch_once()
            if found:
                log.info("Stored %d message(s)", len(found))
        except Exception:
            log.exception("Poll failed, retrying in 5s")
            time.sleep(5)


def start_poller() -> threading.Thread | None:
    if not settings.poll_enabled:
        log.info("Poller disabled (POLL_ENABLED=false)")
        return None
    _stop.clear()
    t = threading.Thread(target=poll_loop, daemon=True, name="sqs-poller")
    t.start()
    return t


def stop_poller() -> None:
    _stop.set()
