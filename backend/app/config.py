from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/postgres"
    supabase_jwt_secret: str = "super-secret-jwt-token-with-at-least-32-characters-long"
    supabase_jwt_algorithms: list[str] = ["HS256"]
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    tracking_base_url: str = "https://contentlab.app/p"
    # Redirect + visitor identity
    visitor_hmac_secret: str = "change-this-secret-in-production-32chars"
    # Comma-separated list of trusted reverse-proxy CIDRs for X-Forwarded-For
    trusted_proxy_cidrs: str = "127.0.0.1/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    visitor_cookie_name: str = "cl_visitor"
    visitor_cookie_max_age: int = 31536000  # 1 year
    redirect_base_url: str = "https://contentlab.app"

    # Phone agent
    phone_agent_url: str = "http://127.0.0.1:9000"
    phone_agent_api_key: str = ""
    tiktok_metrics_provider: str = "fake"  # "fake" | "phone_agent"

    # Worker
    worker_id: str = "worker-1"
    worker_poll_interval: int = 5
    worker_lease_seconds: int = 120
    worker_heartbeat_interval: int = 30

    # Intelligence
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    intelligence_provider: str = "fake"  # "fake" | "claude" | "openrouter"

    # Per-operation model IDs (override via env vars)
    claude_model_generate_hypotheses: str = "claude-sonnet-5"
    claude_model_design_experiment: str = "claude-sonnet-5"
    claude_model_revise_brief: str = "claude-haiku-4-5-20251001"
    claude_model_analyze_experiment: str = "claude-sonnet-5"
    claude_model_generate_candidates: str = "claude-sonnet-5"
    claude_default_timeout: int = 240
    claude_max_tokens: int = 4096



settings = Settings()
