"""Shared Pydantic settings for all Cafe Cloud services."""
from __future__ import annotations
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Base configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service identity
    service_name: str = Field(default="cafe-cloud", alias="SERVICE_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API key (optional security plus)
    api_key: Optional[str] = Field(default=None, alias="API_KEY")

    # PostgreSQL
    postgres_user: str = Field(default="cafe", alias="POSTGRES_USER")
    postgres_password: str = Field(default="cafe_secret", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="cafe_cloud", alias="POSTGRES_DB")

    # RabbitMQ
    rabbitmq_user: str = Field(default="cafe", alias="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="cafe_secret", alias="RABBITMQ_PASSWORD")
    rabbitmq_host: str = Field(default="rabbitmq", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, alias="RABBITMQ_PORT")
    rabbitmq_vhost: str = Field(default="/", alias="RABBITMQ_VHOST")

    # MongoDB
    mongodb_user: str = Field(default="cafe", alias="MONGO_USER")
    mongodb_password: str = Field(default="cafe_secret", alias="MONGO_PASSWORD")
    mongodb_host: str = Field(default="mongodb", alias="MONGO_HOST")
    mongodb_port: int = Field(default=27017, alias="MONGO_PORT")
    mongodb_db: str = Field(default="cafe_cloud", alias="MONGO_DB")

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}{self.rabbitmq_vhost}"
        )

    @property
    def mongodb_url(self) -> str:
        return (
            f"mongodb://{self.mongodb_user}:{self.mongodb_password}"
            f"@{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_db}"
            f"?authSource=admin"
        )


@lru_cache
def get_settings() -> CommonSettings:
    return CommonSettings()
