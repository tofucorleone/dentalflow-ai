from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings


class LlmConfigurationError(RuntimeError):
    """Configuration LLM absente ou invalide."""


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()

    if not settings.openai_api_key:
        raise LlmConfigurationError(
            "OPENAI_API_KEY n'est pas configurée.",
        )

    return AsyncOpenAI(
        api_key=settings.openai_api_key,
    )
