from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "postgresql://username:password@localhost:5432/database_name"
    SQLITE_DATABASE_URL: str = "sqlite:///./options_trading.db"
    
    @property
    def database_url(self) -> str:
        """Get properly formatted database URL"""
        host = os.getenv("PGHOST", "localhost")
        port = os.getenv("PGPORT", "5432")
        database = os.getenv("PGDATABASE", "database_name")
        user = os.getenv("PGUSER", "username")
        password = os.getenv("PGPASSWORD", "password")
        
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(password)
        
        return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"
    
    
    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # AWS settings
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_DYNAMODB_TABLE: str = os.getenv("AWS_DYNAMODB_TABLE", "options_trading_legs")

    # Zerodha settings
    ZERODHA_API_KEY: str = os.getenv("ZERODHA_API_KEY", "")
    ZERODHA_API_SECRET: str = os.getenv("ZERODHA_API_SECRET", "")

    # WebSocket settings
    WEBSOCKET_UPDATE_INTERVAL: int = int(os.getenv("WEBSOCKET_UPDATE_INTERVAL", "2"))

    # Historical Data Service Configuration
    HISTORICAL_MYSQL_HOST: Optional[str] = os.getenv("HISTORICAL_MYSQL_HOST")
    HISTORICAL_MYSQL_PORT: int = int(os.getenv("HISTORICAL_MYSQL_PORT", "3306"))
    HISTORICAL_MYSQL_USER: Optional[str] = os.getenv("HISTORICAL_MYSQL_USER")
    HISTORICAL_MYSQL_PASSWORD: Optional[str] = os.getenv("HISTORICAL_MYSQL_PASSWORD")
    HISTORICAL_MYSQL_DATABASE: Optional[str] = os.getenv("HISTORICAL_MYSQL_DATABASE")
    
    class Config:
        env_file = ".env"
        # Don't override SQLITE_DATABASE_URL from environment if it's empty
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )
        extra = "allow"

settings = Settings() 