from __future__ import annotations
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # --- Soundbox backend Postgres (same names as on-prem-soundbox-backend/.env) ---
    database_type: str = Field(validation_alias="DATABASE_TYPE")
    database_host: str = Field(validation_alias="DATABASE_HOST")
    database_port: int = Field(validation_alias="DATABASE_PORT")
    database_username: str = Field(validation_alias="DATABASE_USERNAME")
    database_password: str = Field(validation_alias="DATABASE_PASSWORD")
    database_name: str = Field(validation_alias="DATABASE_NAME")
    database_ssl_enabled: bool = Field(validation_alias="DATABASE_SSL_ENABLED")

    # --- Merchant field decryption (soundbox-backend typeorm-encrypted) ---
    encryption_key: str = Field(validation_alias="ENCRYPTION_KEY")
    iv: str = Field(validation_alias="IV")
    encryption_method: str = Field(validation_alias="ENCRYPTION_METHOD")

    # --- GCS / Iceberg warehouse (AIML + chanakya pattern) ---
    google_cloud_project: str = Field(validation_alias="GOOGLE_CLOUD_PROJECT")
    gcp_region: str = Field(validation_alias="GCP_REGION")
    gcs_bucket: str = Field(validation_alias="GCS_BUCKET")
    warehouse_path: str = Field(validation_alias="WAREHOUSE_PATH")
    iceberg_namespace: str = Field(validation_alias="ICEBERG_NAMESPACE")
    spark_artifacts_bucket: str = Field(default="", validation_alias="SPARK_ARTIFACTS_BUCKET")

    # --- Ingestion behaviour ---
    ingest_mode: str = Field(validation_alias="INGEST_MODE")
    ingest_batch_size: int = Field(validation_alias="INGEST_BATCH_SIZE")
    watermark_prefix: str = Field(validation_alias="WATERMARK_PREFIX")

    # --- Local staging parquet (DuckDB / AI service reads synced copy) ---
    lakehouse_local_root: str = Field(validation_alias="LAKEHOUSE_LOCAL_ROOT")
    duckdb_threads: int = Field(validation_alias="DUCKDB_THREADS")
    upload_to_gcs: bool = Field(validation_alias="UPLOAD_TO_GCS")
    write_local_parquet: bool = Field(validation_alias="WRITE_LOCAL_PARQUET")

    # --- Ingest engine: pandas (small) | spark (billions of rows) ---
    ingest_engine: str = Field(validation_alias="INGEST_ENGINE")
    spark_app_name: str = Field(validation_alias="SPARK_APP_NAME")
    spark_master: str = Field(validation_alias="SPARK_MASTER")
    spark_iceberg_catalog: str = Field(validation_alias="SPARK_ICEBERG_CATALOG")
    spark_iceberg_version: str = Field(validation_alias="SPARK_ICEBERG_VERSION")
    spark_version: str = Field(validation_alias="SPARK_VERSION")
    spark_jdbc_num_partitions: int = Field(validation_alias="SPARK_JDBC_NUM_PARTITIONS")
    spark_jdbc_fetch_size: int = Field(validation_alias="SPARK_JDBC_FETCH_SIZE")
    spark_decrypt_pii: bool = Field(validation_alias="SPARK_DECRYPT_PII")

    @field_validator("ingest_engine")
    @classmethod
    def validate_ingest_engine(cls, v: str) -> str:
        if v not in ("pandas", "spark"):
            raise ValueError("INGEST_ENGINE must be either 'pandas' or 'spark'")
        return v

    @property
    def jdbc_url(self) -> str:
        base = (
            f"jdbc:postgresql://{self.database_host}:{self.database_port}/"
            f"{self.database_name}"
        )
        if self.database_ssl_enabled:
            return f"{base}?ssl=true&sslmode=require"
        return base

    @property
    def spark_jar_packages(self) -> str:
        """Maven coords loaded by Spark — Iceberg, Postgres JDBC, GCS connector."""
        spark_scala = "2.12"
        iceberg = self.spark_iceberg_version
        spark_ver = self.spark_version
        return ",".join(
            [
                f"org.apache.iceberg:iceberg-spark-runtime-{spark_ver}_{spark_scala}:{iceberg}",
                "org.postgresql:postgresql:42.7.2",
                "com.google.cloud.bigdataoss:gcs-connector:hadoop3-2.2.19",
            ]
        )

    @property
    def iceberg_table_prefix(self) -> str:
        return f"{self.spark_iceberg_catalog}.{self.iceberg_namespace}"

    @property
    def warehouse_uri(self) -> str:
        if self.warehouse_path:
            return self.warehouse_path.rstrip("/")
        if self.gcs_bucket:
            return f"gs://{self.gcs_bucket.strip('/')}"
        return ""



    def require_database(self) -> None:
        missing = [
            name
            for name, value in {
                "DATABASE_HOST": self.database_host,
                "DATABASE_USERNAME": self.database_username,
                "DATABASE_PASSWORD": self.database_password,
                "DATABASE_NAME": self.database_name,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required database environment variables: " + ", ".join(missing)
            )

    def require_gcs(self) -> None:
        if not self.warehouse_uri:
            raise RuntimeError("Set WAREHOUSE_PATH or GCS_BUCKET for GCS Iceberg upload")


@lru_cache
def get_settings() -> Settings:
    return Settings()
