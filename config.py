"""
Configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # SMTP Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    from_email: str
    
    # Balancer API Configuration
    balancer_v3_api: str = "https://api-v3.balancer.fi/"
    # V2 subgraph - using public endpoint
    balancer_v2_subgraph: str = "https://api.studio.thegraph.com/query/24660/balancer-ethereum-v2/version/latest"
    # Optional: Unified Balancer GraphQL endpoint (if you have one)
    balancer_gql_endpoint: str | None = None
    default_chain: str = "MAINNET"  # For API queries (e.g., MAINNET, ARBITRUM, POLYGON)
    blockchain_name: str = "ethereum"  # For balancer.fi URLs (e.g., ethereum, arbitrum, polygon)

    # Telegram Config
    telegram_bot_token: str
    telegram_chat_id: str
    
    # Database Configuration
    # Railway and other platforms inject DATABASE_URL automatically
    database_url: str = "postgresql://localhost:5432/pool_report"
    
    # Optional default pool
    default_pool_address: str | None = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
