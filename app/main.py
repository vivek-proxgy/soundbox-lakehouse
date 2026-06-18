"""CLI entrypoint — routes to pandas or PySpark engine via INGEST_ENGINE env."""

import os
from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    if settings.ingest_engine == "spark":
        is_cloud_run = "K_SERVICE" in os.environ
        run_on_dataproc = os.environ.get("DATAPROC_SERVERLESS", "false").lower() == "true"

        if is_cloud_run or run_on_dataproc:
            from app.job.run_dataproc_orchestration import run as run_dataproc

            result = run_dataproc(settings)
        else:
            from app.job.run_spark_ingestion import run as run_spark

            result = run_spark(settings)
    else:
        from app.job.run_ingestion import run as run_pandas

        result = run_pandas(settings)
    print(result)


if __name__ == "__main__":
    main()

