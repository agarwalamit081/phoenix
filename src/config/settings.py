"""Application configuration settings using Pydantic Settings."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure environment variables are loaded from .env via python-dotenv first.
load_dotenv()


def parse_cors_origins(v: str | list[str]) -> list[str]:
    """Parse CORS origins from environment variable."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return [origin.strip() for origin in v.split(",")]
    return v


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="phoenix-ai-travel-companion", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: Literal["development", "staging", "production", "testing"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Database - PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://ai_travel_companion:trainer@localhost:5432/ai_travel_companion",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=3600, alias="DATABASE_POOL_RECYCLE")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_pool_size: int = Field(default=10, alias="REDIS_POOL_SIZE")
    redis_decode_responses: bool = Field(default=True, alias="REDIS_DECODE_RESPONSES")

    # Neo4j Knowledge Graph
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    # ==========================================
    # PRIMARY LLM PROVIDERS
    # ==========================================

    # OpenAI (Primary for chat and embeddings)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model_chat: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL_CHAT")
    openai_model_complex: str = Field(default="gpt-4o", alias="OPENAI_MODEL_COMPLEX")
    openai_model_embedding: str = Field(default="text-embedding-3-small", alias="OPENAI_MODEL_EMBEDDING")
    openai_max_tokens: int = Field(default=4096, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash-exp", alias="GEMINI_MODEL")

    # DeepSeek
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    # GLM (Zhipu AI)
    glm_api_key: str = Field(default="", alias="GLM_API_KEY")
    glm_model: str = Field(default="glm-4-flash", alias="GLM_MODEL")

    # Cohere
    cohere_api_key: str = Field(default="", alias="COHERE_API_KEY")
    cohere_model_embedding: str = Field(default="embed-v3.0", alias="COHERE_MODEL_EMBEDDING")
    cohere_model_chat: str = Field(default="command-r-plus", alias="COHERE_MODEL_CHAT")

    # ==========================================
    # AI AGENT & PLANNING
    # ==========================================

    # Voyage AI (Route planning)
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")

    # Backboard (Agent planning)
    backboard_api_key: str = Field(default="", alias="BACKBOARD_API_KEY")

    # ==========================================
    # SEARCH & DISCOVERY
    # ==========================================

    # Tavily (AI-powered search)
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # SerpApi (Google Search results)
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")

    # ==========================================
    # VOICE & AUDIO
    # ==========================================

    # API Keys - Speechmatics
    speechmatics_api_key: str = Field(default="", alias="SPEECHMATICS_API_KEY")
    speechmatics_ws_url: str = Field(
        default="wss://eu2.rt.speechmatics.com/v2", alias="SPEECHMATICS_WS_URL"
    )
    speechmatics_auto_detect: bool = Field(default=True, alias="SPEECHMATICS_AUTO_DETECT")
    speechmatics_language: str = Field(default="en", alias="SPEECHMATICS_LANGUAGE")

    # ElevenLabs (Text-to-Speech)
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_model: str = Field(default="eleven_multilingual_v2", alias="ELEVENLABS_MODEL")
    elevenlabs_voice: str = Field(default="Rachel", alias="ELEVENLABS_VOICE")

    # API Keys - LiveKit
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")
    livekit_url: str = Field(default="", alias="LIVEKIT_URL")

    # ==========================================
    # MAP INTEGRATION (MCP)
    # ==========================================

    map_provider: str = Field(default="mcp", alias="MAP_PROVIDER")
    mcp_server_url: str = Field(default="http://localhost:3000/mcp", alias="MCP_SERVER_URL")

    # Fallback: Direct Google Maps API
    google_maps_api_key: str = Field(default="", alias="GOOGLE_MAPS_API_KEY")

    # Security
    secret_key: str = Field(default="", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # OAuth Providers
    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    apple_oauth_client_id: str = Field(default="", alias="APPLE_OAUTH_CLIENT_ID")
    apple_oauth_team_id: str = Field(default="", alias="APPLE_OAUTH_TEAM_ID")
    apple_oauth_key_id: str = Field(default="", alias="APPLE_OAUTH_KEY_ID")
    apple_oauth_private_key: str = Field(default="", alias="APPLE_OAUTH_PRIVATE_KEY")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default=["*"], alias="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(default=["*"], alias="CORS_ALLOW_HEADERS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from environment variable."""
        return parse_cors_origins(v)

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, alias="RATE_LIMIT_PERIOD")
    rate_limit_redis_prefix: str = Field(default="rate_limit", alias="RATE_LIMIT_REDIS_PREFIX")

    # Feature Flags
    enable_voice: bool = Field(default=True, alias="ENABLE_VOICE")
    enable_translation: bool = Field(default=True, alias="ENABLE_TRANSLATION")
    enable_social_intelligence: bool = Field(default=False, alias="ENABLE_SOCIAL_INTELLIGENCE")
    enable_guided_tour: bool = Field(default=True, alias="ENABLE_GUIDED_TOUR")
    enable_route_optimization: bool = Field(default=True, alias="ENABLE_ROUTE_OPTIMIZATION")

    # Voice Settings
    supported_languages: str = Field(default="en,zh,ja,ko,hi,fr", alias="SUPPORTED_LANGUAGES")
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    voice_activity_detection: bool = Field(default=True, alias="VOICE_ACTIVITY_DETECTION")
    speaker_diarization: bool = Field(default=True, alias="SPEAKER_DIARIZATION")

    @property
    def supported_languages_list(self) -> list[str]:
        """Get supported languages as a list."""
        return self.supported_languages.split(",")

    # Translation Settings
    translation_cache_ttl: int = Field(default=86400, alias="TRANSLATION_CACHE_TTL")
    translation_batch_size: int = Field(default=10, alias="TRANSLATION_BATCH_SIZE")

    # Route Planning
    route_max_pois: int = Field(default=20, alias="ROUTE_MAX_POIS")
    route_max_distance_km: int = Field(default=50, alias="ROUTE_MAX_DISTANCE_KM")
    route_optimization_timeout: int = Field(default=30, alias="ROUTE_OPTIMIZATION_TIMEOUT")

    # Tour Settings
    tour_proximity_threshold_meters: int = Field(default=50, alias="TOUR_PROXITY_THRESHOLD_METERS")
    tour_state_sync_interval_seconds: int = Field(default=5, alias="TOUR_STATE_SYNC_INTERVAL_SECONDS")
    tour_auto_resume_minutes: int = Field(default=10, alias="TOUR_AUTO_RESUME_MINUTES")

    # Social Intelligence
    social_reddit_client_id: str = Field(default="", alias="SOCIAL_REDDIT_CLIENT_ID")
    social_reddit_client_secret: str = Field(default="", alias="SOCIAL_REDDIT_CLIENT_SECRET")
    social_twitter_bearer_token: str = Field(default="", alias="SOCIAL_TWITTER_BEARER_TOKEN")
    social_signal_cache_ttl: int = Field(default=900, alias="SOCIAL_SIGNAL_CACHE_TTL")
    social_update_interval_minutes: int = Field(default=15, alias="SOCIAL_UPDATE_INTERVAL_MINUTES")

    # Map Providers (using MCP for Google Maps)
    # Mapbox is optional and not configured by default
    mapbox_access_token: str = Field(default="", alias="MAPBOX_ACCESS_TOKEN")
    google_maps_api_key: str = Field(default="", alias="GOOGLE_MAPS_API_KEY")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "text"] = Field(default="json", alias="LOG_FORMAT")
    log_file_path: str = Field(default="logs/phoenix.log", alias="LOG_FILE_PATH")
    log_rotation: str = Field(default="100 MB", alias="LOG_ROTATION")
    log_retention: str = Field(default="30 days", alias="LOG_RETENTION")

    # Monitoring
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    metrics_port: int = Field(default=9090, alias="METRICS_PORT")
    health_check_enabled: bool = Field(default=True, alias="HEALTH_CHECK_ENABLED")
    health_check_interval_seconds: int = Field(default=30, alias="HEALTH_CHECK_INTERVAL_SECONDS")

    # Performance
    cache_default_ttl: int = Field(default=3600, alias="CACHE_DEFAULT_TTL")
    cache_max_size: int = Field(default=10000, alias="CACHE_MAX_SIZE")
    connection_timeout: int = Field(default=30, alias="CONNECTION_TIMEOUT")
    read_timeout: int = Field(default=60, alias="READ_TIMEOUT")
    write_timeout: int = Field(default=60, alias="WRITE_TIMEOUT")

    # Testing
    test_database_url: str = Field(
        default="postgresql+asyncpg://ai_travel_companion:trainer@localhost:5432/ai_travel_companion_test",
        alias="TEST_DATABASE_URL",
    )
    test_redis_url: str = Field(default="redis://localhost:6379/1", alias="TEST_REDIS_URL")
    test_neo4j_uri: str = Field(default="bolt://localhost:7687", alias="TEST_NEO4J_URI")
    test_neo4j_user: str = Field(default="neo4j", alias="TEST_NEO4J_USER")
    test_neo4j_password: str = Field(default="neo4j", alias="TEST_NEO4J_PASSWORD")

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return self.database_url.replace("+asyncpg", "").replace("asyncpg", "postgresql+psycopg2")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings: Settings = get_settings()
