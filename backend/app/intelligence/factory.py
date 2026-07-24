"""
Provider factory — selects FakeIntelligenceProvider or AnthropicIntelligenceProvider
based on settings.intelligence_provider.
"""
from app.config import settings


def get_intelligence_provider():
    """
    Returns the configured intelligence provider.
    INTELLIGENCE_PROVIDER=fake  → FakeIntelligenceProvider (default)
    INTELLIGENCE_PROVIDER=claude → AnthropicIntelligenceProvider
    """
    if settings.intelligence_provider == "claude":
        from app.intelligence.anthropic_provider import AnthropicIntelligenceProvider
        return AnthropicIntelligenceProvider()
    from app.intelligence.fake import FakeIntelligenceProvider
    return FakeIntelligenceProvider()
