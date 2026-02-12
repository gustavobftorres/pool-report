"""
Configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Balancer API Configuration (only needed for FastAPI backend)
    balancer_v3_api: str = "https://api-v3.balancer.fi/"
    # V2 subgraph - using public endpoint
    balancer_v2_subgraph: str = "https://api.studio.thegraph.com/query/24660/balancer-ethereum-v2/version/latest"
    # Optional: Unified Balancer GraphQL endpoint (if you have one)
    balancer_gql_endpoint: str | None = None
    default_chain: str = "MAINNET"  # For API queries (e.g., MAINNET, ARBITRUM, POLYGON)
    blockchain_name: str = "ethereum"  # For balancer.fi URLs (e.g., ethereum, arbitrum, polygon)

    # Telegram Config (only needed for FastAPI backend)
    telegram_bot_token: str | None = None
    
<<<<<<< HEAD
    # Notion API Configuration
    notion_api_key: str | None = None
    
    # Database Configuration (optional - no longer used, kept for backwards compatibility)
    database_url: str | None = None
=======
    # OpenAI Configuration (for insights generation)
    openai_api_key: str | None = None
    enable_insights: bool = True
    # Multi-agent insights models
    openai_orchestrator_model: str = "gpt-4o-mini"
    openai_specialist_model: str = "gpt-4o"
    openai_summarizer_model: str = "gpt-4o-mini"
    # Docs / grounding options
    enable_insights_live_docs: bool = False
    insights_docs_base_urls: list[str] | None = None
    insights_max_doc_chars: int = 6000

    # DEX Benchmarking (GeckoTerminal)
    gecko_base_url: str = "https://api.geckoterminal.com/api/v2"
    dex_benchmark_enabled: bool = True
    dex_benchmark_top_n: int = 3
    dex_benchmark_timeout: float = 10.0
    
    # Dune API Configuration
    dune_api_key: str | None = None
    dune_query_performance: str = "medium"  # "low", "medium", "high"
    dune_query_timeout: float = 60.0
    dune_anchor_volume_query_id: int | None = None
    
    # CoinGecko API (no key required for free tier)
    coingecko_rate_limit: int = 50  # calls per minute
>>>>>>> @gbr/feat/takeaways
    
    # Optional default pool
    default_pool_address: str | None = None

    # Notion API Configuration
    notion_api_key: str | None = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

<<<<<<< HEAD
    # Dune API Configuration
    dune_api_key: str | None = None
    dune_query_performance: str = "medium"  # "low", "medium", "high"
    dune_query_timeout: float = 60.0

# Global settings instance
=======
>>>>>>> @gbr/feat/takeaways
settings = Settings()
