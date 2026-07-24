"""
Provider factory — selects FakeIntelligenceProvider or AnthropicIntelligenceProvider
based on settings.intelligence_provider.
"""
from app.config import settings


def get_intelligence_provider():
    _env = settings.environment
    _prov = settings.intelligence_provider
    # Production: only claude
    if _env == "production" and _prov != "claude":
        raise RuntimeError("INTELLIGENCE_PROVIDER must be 'claude' in production.")
    # Staging: provider must be explicitly set (not from missing env var default)
    if _env == "staging" and not _prov:
        raise RuntimeError(
            "INTELLIGENCE_PROVIDER must be explicitly set in staging. "
            "No implicit default is permitted outside development and test."
        )
    # Test: fake is expected
    # Development: fake or claude, both valid

    # Production must use Claude explicitly — never silently serve fixture data
    if settings.environment == "production" and settings.intelligence_provider != "claude":
        raise RuntimeError(
            "INTELLIGENCE_PROVIDER must be 'claude' in production. "
            "Serving fixture intelligence in production is not permitted."
        )

    """
    Returns the configured intelligence provider.
    INTELLIGENCE_PROVIDER=fake  → FakeIntelligenceProvider (default)
    INTELLIGENCE_PROVIDER=claude → AnthropicIntelligenceProvider
    """
    prov = settings.intelligence_provider
    if prov == "claude":
        from app.intelligence.anthropic_provider import AnthropicIntelligenceProvider
        return AnthropicIntelligenceProvider()
    if prov == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when INTELLIGENCE_PROVIDER=openrouter")
        from app.intelligence.openrouter_provider import OpenRouterIntelligenceProvider
        return OpenRouterIntelligenceProvider()
    from app.intelligence.fake import FakeIntelligenceProvider
    return FakeIntelligenceProvider()
