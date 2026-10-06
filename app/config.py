import os


class Settings:
    def __init__(self) -> None:
        self.aws_region: str = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
        # Set this for local testing against elasticmq / localstack, e.g. http://elasticmq:9324
        self.aws_endpoint_url: str | None = os.getenv("AWS_ENDPOINT_URL") or None
        self.sqs_queue_url: str = os.getenv("SQS_QUEUE_URL", "")

        self.poll_enabled: bool = os.getenv("POLL_ENABLED", "true").lower() in ("1", "true", "yes")
        self.wait_time_seconds: int = int(os.getenv("WAIT_TIME_SECONDS", "20"))
        self.visibility_timeout: int = int(os.getenv("VISIBILITY_TIMEOUT", "300"))
        self.max_messages: int = int(os.getenv("MAX_MESSAGES", "10"))
        # Delete message from SQS after it has been stored locally.
        self.delete_after_store: bool = os.getenv("DELETE_AFTER_STORE", "true").lower() in ("1", "true", "yes")

        self.db_path: str = os.getenv("DB_PATH", "/data/jobs.db")


settings = Settings()
