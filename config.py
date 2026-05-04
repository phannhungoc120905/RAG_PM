from functools import lru_cache

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        password_part = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return (
            f"mysql+pymysql://{self.DB_USER}{password_part}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
