from __future__ import annotations
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.enums.env_var import SettingsEnv
from app.core.enums.run_mode import DEFAULT_BIND_HOST, RunMode, ServerDefaults

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

    # --- API server security (on-prem-soundbox-backend compatible) ---
    auth_enabled: bool = Field(default=True, validation_alias="AUTH_ENABLED")
    auth_api_key_only: bool = Field(default=False, validation_alias="AUTH_API_KEY_ONLY")
    auth_jwt_secret: str = Field(default="", validation_alias="AUTH_JWT_SECRET")
    lakehouse_api_key: str = Field(default="", validation_alias="LAKEHOUSE_API_KEY")
    cors_enabled: bool = Field(default=True, validation_alias="CORS_ENABLED")
    allowed_origins: str = Field(
        default="http://localhost:3000",
        validation_alias="ALLOWED_ORIGINS",
    )
    throttle_limit: int = Field(default=100, validation_alias="THROTTLE_LIMIT")
    throttle_ttl: int = Field(default=60, validation_alias="THROTTLE_TTL")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    sql_max_length: int = Field(default=10000, validation_alias="SQL_MAX_LENGTH")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    service_user_id: str = Field(default="service", validation_alias="SERVICE_USER_ID")
    anonymous_user_id: str = Field(default="anonymous", validation_alias="ANONYMOUS_USER_ID")
    conversation_max_turns: int = Field(default=20, validation_alias="CONVERSATION_MAX_TURNS")
    conversation_max_message_length: int = Field(
        default=4000,
        validation_alias="CONVERSATION_MAX_MESSAGE_LENGTH",
    )
    llm_context_window: int = Field(default=6, validation_alias="LLM_CONTEXT_WINDOW")

    # --- Process mode (required — no auto-detection from PORT or CLI) ---
    run_mode: RunMode = Field(validation_alias=SettingsEnv.RUN_MODE)

    # --- API server runtime ---
    server_host: str = Field(
        default=DEFAULT_BIND_HOST,
        validation_alias=SettingsEnv.SERVER_HOST,
    )
    server_port: int = Field(
        default=ServerDefaults.PORT,
        validation_alias=SettingsEnv.PORT,
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @field_validator("run_mode", mode="before")
    @classmethod
    def validate_run_mode(cls, value: object) -> RunMode:
        if value is None or str(value).strip() == "":
            raise ValueError(
                f"{SettingsEnv.RUN_MODE} is required — set to "
                f"'{RunMode.SERVER}' or '{RunMode.INGEST}'"
            )
        normalized = str(value).lower().strip()
        try:
            return RunMode(normalized)
        except ValueError as exc:
            allowed = ", ".join(RunMode.values())
            raise ValueError(
                f"{SettingsEnv.RUN_MODE}={value!r} is invalid — must be one of: {allowed}"
            ) from exc

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
