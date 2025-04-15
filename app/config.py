import os
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Aplikācijas konfigurācija
    APP_NAME: str = "RSS Collection Service"
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    
    # Datubāzes konfigurācija
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_DB: str
    
    # Celery konfigurācija
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # RSS ievākšanas konfigurācija
    RSS_COLLECTION_INTERVAL: int = 2  # minūtes
    RSS_CONCURRENT_REQUESTS: int = 2   # vienlaicīgo pieprasījumu skaits
    RSS_REQUEST_TIMEOUT: int = 10      # pieprasījuma noilgums sekundēs
    
    # Izveidojam datubāzes URL no komponentēm
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            path=self.POSTGRES_DB,
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Izveidojam iestatījumu instanci
settings = Settings()