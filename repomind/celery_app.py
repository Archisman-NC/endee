from celery import Celery

celery_app = Celery(
    "repomind",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["ingestion.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
    result_extended=True
)

if __name__ == "__main__":
    celery_app.start()
