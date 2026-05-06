from functools import lru_cache
from pathlib import Path

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ".env.example"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "RAG_PM"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Internal SSO
    SSO_ENABLED: bool = True
    SSO_PROVIDER_NAME: str = "internal_mock"
    SSO_SHARED_SECRET: str = "change-me-sso"
    SSO_AUTO_CREATE_USERS: bool = True

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "ragpm"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # AI model
    MODEL_NAME: str = "llama3.2"
    MODEL_PATH: str = "/models/llama3.2"
    EMBEDDING_MODEL_NAME: str = "local-hash-384"
    OCR_USE_SENTENCE_TRANSFORMERS: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT_SECONDS: int = 180
    FAISS_INDEX_PATH: str = "./faiss_index"
    VECTOR_DIM: int = 4096
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100
    OCR_LANG: str = "vie"

    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Backup
    BACKUP_DIR: str = "./backups"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> bool | object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return value

    @field_validator("MODEL_PATH", "FAISS_INDEX_PATH", "UPLOAD_DIR", "BACKUP_DIR", mode="after")
    @classmethod
    def resolve_project_relative_paths(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((BASE_DIR / path).resolve())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        password_part = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return (
            f"mysql+pymysql://{self.DB_USER}{password_part}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def OLLAMA_GENERATE_URL(self) -> str:
        return f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/generate"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def OLLAMA_TAGS_URL(self) -> str:
        return f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/tags"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
