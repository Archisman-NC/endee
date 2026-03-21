from celery import Celery

import os

celery_app = Celery(
    "repomind",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=["ingestion.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
    result_extended=True
)

if __name__ == "__main__":
    celery_app.start()
