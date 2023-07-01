from enum import Enum

from pydantic import BaseSettings


class Environment(str, Enum):
    PRODUCTION = "prod"
    DEVELOPMENT = "dev"


class Settings(BaseSettings):
    SQLITEDB_PATH: str = "filmswap.db"
    SQL_ECHO: bool = False
    GUILD_ID: int = -1
    ALLOWED_ROLES: list[str] = []
    ROLE: str = "film-swap"
    ENVIRONMENT: str = Environment.DEVELOPMENT
    BACKUP_DIR: str = "backups"

    class Config:
        case_sensitive = False
        env_file = ".env"


settings = Settings()
