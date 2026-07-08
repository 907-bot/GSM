"""
LLM Service — Free-tier providers only.

Priority:
  1. Groq  (cloud, free tier — https://console.groq.com/keys)
  2. Ollama (local,  fully free — https://ollama.com)
  3. HuggingFace Inference API (free tier — https://huggingface.co/settings/tokens)

No OpenAI or Anthropic keys required.
"""

from typing import List, Dict, Any, Optional
import structlog
from ..config import settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Groq models available on the free tier (as of 2024-2025)
# ---------------------------------------------------------------------------
GROQ_FREE_MODELS = [
    "llama-3.3-70b-versatile",   # best quality on free tier
    "llama-3.1-8b-instant",      # faster / lower latency
    "mixtral-8x7b-32768",        # large context window
    "gemma2-9b-it",              # Google Gemma 2
    "llama-3.1-70b-versatile",   # alternative large model
]

# Ollama models (pulled locally — 100% free, no API key)
OLLAMA_FREE_MODELS = [
    "llama3",          # Meta Llama 3 8B
    "mistral",         # Mistral 7B
    "gemma2",          # Google Gemma 2 9B
    "phi3",            # Microsoft Phi-3
    "qwen2.5",         # Alibaba Qwen 2.5
    "deepseek-r1",     # DeepSeek R1 (reasoning)
]

# OpenRouter free models (https://openrouter.ai — register for free API key)
OPENROUTER_FREE_MODELS = [
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "openchat/openchat-3.5-0106:free",
]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMService:
    """
    Unified LLM client that routes to free-tier providers.
    Provider order: groq → ollama → huggingface
    """

    def __init__(self):
        self.provider = settings.DEFAULT_LLM_PROVIDER
        self.model = settings.DEFAULT_LLM_MODEL
        self._groq_client = None
        self._ollama_client = None

    # ------------------------------------------------------------------
    # Internal client initialisation (lazy)
    # ------------------------------------------------------------------

    def _get_groq_client(self):
        """Return a cached Groq client (lazy init)."""
        if self._groq_client is None:
            try:
                from groq import Groq  # type: ignore
                if not settings.GROQ_API_KEY:
                    raise ValueError(
                        "GROQ_API_KEY is not set. "
                        "Get a free key at https://console.groq.com/keys"
                    )
                self._groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq client initialised", model=self.model)
            except ImportError:
                logger.warning("groq package not installed; falling back to Ollama")
        return self._groq_client

    def _get_ollama_client(self):
        """Return a cached Ollama client (lazy init)."""
        if self._ollama_client is None:
            try:
                import ollama  # type: ignore
                self._ollama_client = ollama
                logger.info(
                    "Ollama client initialised",
                    endpoint=settings.OLLAMA_ENDPOINT,
                )
            except ImportError:
                logger.warning("ollama package not installed")
        return self._ollama_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Send a chat completion request to the configured provider.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            model:    Override the default model for this call.
            temperature: Sampling temperature (0–1).
            max_tokens: Maximum tokens to generate.

        Returns:
            Assistant reply as a plain string.
        """
        target_model = model or self.model

        if self.provider == "groq":
            return await self._chat_groq(messages, target_model, temperature, max_tokens)
        elif self.provider == "ollama":
            return await self._chat_ollama(messages, target_model, temperature, max_tokens)
        elif self.provider == "huggingface":
            return await self._chat_huggingface(messages, target_model, temperature, max_tokens)
        elif self.provider == "openrouter":
            return await self._chat_openrouter(messages, target_model, temperature, max_tokens)
        else:
            logger.warning(
                "Unknown provider, falling back to Groq",
                provider=self.provider,
            )
            return await self._chat_groq(messages, target_model, temperature, max_tokens)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Convenience wrapper: build messages from a single prompt and call chat().
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _chat_groq(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Groq cloud inference — free tier, no credit card needed."""
        try:
            client = self._get_groq_client()
            if client is None:
                logger.warning("Groq unavailable, falling back to Ollama")
                return await self._chat_ollama(messages, OLLAMA_FREE_MODELS[0], temperature, max_tokens)

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            logger.info("Groq chat completed", model=model, tokens=response.usage.total_tokens)
            return content or ""

        except Exception as e:
            logger.error("Groq chat failed, falling back to Ollama", error=str(e))
            return await self._chat_ollama(messages, OLLAMA_FREE_MODELS[0], temperature, max_tokens)

    async def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ollama local inference — 100% free, runs on your machine."""
        try:
            ollama = self._get_ollama_client()
            if ollama is None:
                raise RuntimeError("Ollama client not available")

            import httpx

            # Use Ollama's OpenAI-compatible chat endpoint
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.post(
                    f"{settings.OLLAMA_ENDPOINT}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                logger.info("Ollama chat completed", model=model)
                return content

        except Exception as e:
            logger.error("Ollama chat failed", error=str(e), endpoint=settings.OLLAMA_ENDPOINT)
            raise RuntimeError(
                f"All LLM providers failed. Last error: {e}\n"
                "Tip: Make sure Ollama is running (`ollama serve`) "
                "or set GROQ_API_KEY in your .env file."
            ) from e

    async def _chat_huggingface(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """HuggingFace Inference API — free tier available."""
        try:
            import httpx

            if not settings.HUGGINGFACE_API_KEY:
                raise ValueError(
                    "HUGGINGFACE_API_KEY is not set. "
                    "Get a free token at https://huggingface.co/settings/tokens"
                )

            # Convert chat messages to a single prompt string for HF API
            prompt = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in messages
            ) + "\nASSISTANT:"

            hf_model = model or "mistralai/Mistral-7B-Instruct-v0.3"
            api_url = f"https://api-inference.huggingface.co/models/{hf_model}"

            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.post(
                    api_url,
                    headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": max_tokens,
                            "temperature": temperature,
                            "return_full_text": False,
                        },
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                if isinstance(result, list) and result:
                    return result[0].get("generated_text", "")
                return ""

        except Exception as e:
            logger.error("HuggingFace chat failed", error=str(e))
            raise

    async def _chat_openrouter(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        OpenRouter — free frontier models.
        Get a free key at https://openrouter.ai
        Free models include: mistralai/mistral-7b-instruct:free, meta-llama/llama-3.1-8b-instruct:free
        """
        try:
            import httpx

            api_key = getattr(settings, "OPENROUTER_API_KEY", None)
            if not api_key:
                logger.warning("OPENROUTER_API_KEY not set, falling back to Groq")
                return await self._chat_groq(messages, GROQ_FREE_MODELS[0], temperature, max_tokens)

            target_model = model if model in OPENROUTER_FREE_MODELS else OPENROUTER_FREE_MODELS[0]

            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://gsm-os.research",
                        "X-Title": "GSM-OS Scientific Discovery Platform",
                    },
                    json={
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("OpenRouter chat completed", model=target_model)
                return content or ""

        except Exception as e:
            logger.error("OpenRouter chat failed, falling back to Groq", error=str(e))
            return await self._chat_groq(messages, GROQ_FREE_MODELS[0], temperature, max_tokens)

    # ------------------------------------------------------------------
    # Streaming (for real-time summarization)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ):
        """
        Stream a chat completion — yields token strings.
        Uses Groq streaming or Ollama streaming.
        """
        target_model = model or self.model

        if self.provider == "groq":
            async for token in self._stream_groq(messages, target_model, temperature, max_tokens):
                yield token
        elif self.provider == "ollama":
            async for token in self._stream_ollama(messages, target_model, temperature, max_tokens):
                yield token
        else:
            async for token in self._stream_groq(messages, target_model, temperature, max_tokens):
                yield token

    async def _stream_groq(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        """Stream from Groq API."""
        try:
            client = self._get_groq_client()
            if client is None:
                async for token in self._stream_ollama(messages, model, temperature, max_tokens):
                    yield token
                return

            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error("Groq stream failed, falling back to Ollama", error=str(e))
            async for token in self._stream_ollama(messages, model, temperature, max_tokens):
                yield token

    async def _stream_ollama(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        """Stream from Ollama."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as http:
                async with http.stream(
                    "POST",
                    f"{settings.OLLAMA_ENDPOINT}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.strip():
                            import json
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
        except Exception as e:
            logger.error("Ollama stream failed", error=str(e))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_available_models(self) -> Dict[str, List[str]]:
        """Return free models available per provider."""
        return {
            "groq": GROQ_FREE_MODELS,
            "ollama": OLLAMA_FREE_MODELS,
            "openrouter": OPENROUTER_FREE_MODELS,
            "huggingface": [
                "mistralai/Mistral-7B-Instruct-v0.3",
                "meta-llama/Llama-3.1-8B-Instruct",
                "google/gemma-2-9b-it",
                "microsoft/Phi-3-mini-4k-instruct",
            ],
        }

    def get_langchain_llm(self, **kwargs: Any):
        """
        Return a LangChain-compatible LLM object for use in chains/agents.
        Uses ChatGroq (free) by default, falls back to ChatOllama.
        """
        if self.provider == "groq":
            try:
                from langchain_groq import ChatGroq  # type: ignore
                return ChatGroq(
                    groq_api_key=settings.GROQ_API_KEY,
                    model_name=self.model,
                    **kwargs,
                )
            except Exception as e:
                logger.warning("ChatGroq unavailable, using Ollama", error=str(e))

        # Fallback: Ollama via langchain-community
        try:
            from langchain_community.llms import Ollama  # type: ignore
            return Ollama(
                base_url=settings.OLLAMA_ENDPOINT,
                model=OLLAMA_FREE_MODELS[0],
                **kwargs,
            )
        except Exception as e:
            logger.error("No LangChain LLM available", error=str(e))
            raise RuntimeError("Could not create a LangChain LLM. Install groq or ollama.") from e


# Singleton instance — import this everywhere instead of OpenAI/Anthropic clients
llm_service = LLMService()
