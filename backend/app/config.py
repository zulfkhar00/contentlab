from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_jwt_secret: str = "super-secret-jwt-token-with-at-least-32-characters-long"
    supabase_jwt_algorithms: list[str] = ["HS256"]
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    tracking_base_url: str = "https://contentlab.app/p"
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
    claude_default_timeout: int = 60
    claude_max_tokens: int = 4096



settings = Settings()
