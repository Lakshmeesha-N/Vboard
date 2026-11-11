"""
app/providers/factory.py

Provider factory for the multi-provider AI abstraction layer.

Call get_stt_provider() / get_llm_provider() to obtain the active
provider instance selected by settings.STT_PROVIDER / settings.LLM_PROVIDER.

Both functions are intentionally stateless (no singleton caching) so that
the provider selection can be changed between requests in tests without
needing lifespan restarts.  The underlying HTTP clients inside each
provider already handle connection pooling.
"""

from __future__ import annotations

from app.core.config import settings
from app.providers.base import BaseLLMProvider, BaseSTTProvider


def get_stt_provider() -> BaseSTTProvider:
    """
    Return the active STT provider instance.

    Provider is selected by settings.STT_PROVIDER:
        "meta"    → MetaSTTProvider    (default, uses Meta Muse ASR)
        "sarvam"  → SarvamSTTProvider  (Sarvam AI Saaras, great for Indian languages)
        "openai"  → OpenAIWhisperSTTProvider (OpenAI Whisper)

    Raises:
        ValueError: If settings.STT_PROVIDER is not a known value.
    """
    provider = (settings.STT_PROVIDER or "meta").lower().strip()

    if provider == "meta":
        from app.providers.stt.meta import MetaSTTProvider
        return MetaSTTProvider()

    if provider == "sarvam":
        from app.providers.stt.sarvam import SarvamSTTProvider
        return SarvamSTTProvider()

    if provider == "openai":
        from app.providers.stt.openai_whisper import OpenAIWhisperSTTProvider
        return OpenAIWhisperSTTProvider()

    raise ValueError(
        f"Unknown STT_PROVIDER '{settings.STT_PROVIDER}'. "
        "Valid values: meta, sarvam, openai"
    )


def get_llm_provider() -> BaseLLMProvider:
    """
    Return the active LLM provider instance.

    Provider is selected by settings.LLM_PROVIDER:
        "meta"    → OpenAICompatibleLLMProvider pointed at Meta BASE_URL  (default)
        "openai"  → OpenAICompatibleLLMProvider pointed at OpenAI
        "groq"    → OpenAICompatibleLLMProvider pointed at Groq
        "google"  → GoogleGeminiLLMProvider

    Raises:
        ValueError: If settings.LLM_PROVIDER is not a known value.
    """
    provider = (settings.LLM_PROVIDER or "meta").lower().strip()

    if provider == "meta":
        from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
        return OpenAICompatibleLLMProvider(
            api_key=settings.META_API_KEY or "none",
            base_url=settings.META_BASE_URL or "https://api.meta.ai/v1",
            model=settings.DEFAULT_LLM_MODEL or "muse-spark-1.3",
            timeout=20.0,
            max_retries=1,
            use_shared_meta_client=True,
        )

    if provider == "openai":
        from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
        return OpenAICompatibleLLMProvider(
            api_key=settings.OPENAI_API_KEY or "none",
            base_url=settings.OPENAI_BASE_URL or None,
            model=settings.OPENAI_LLM_MODEL,
            timeout=20.0,
            max_retries=1,
        )

    if provider == "groq":
        from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
        return OpenAICompatibleLLMProvider(
            api_key=settings.GROQ_API_KEY or "none",
            base_url=settings.GROQ_BASE_URL,
            model=settings.GROQ_LLM_MODEL,
            timeout=20.0,
            max_retries=1,
        )

    if provider == "google":
        from app.providers.llm.gemini import GoogleGeminiLLMProvider
        return GoogleGeminiLLMProvider(
            api_key=settings.GEMINI_API_KEY or "",
            model=settings.GEMINI_LLM_MODEL,
            timeout=25.0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
        "Valid values: meta, openai, groq, google"
    )

