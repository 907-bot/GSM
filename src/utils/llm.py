"""
LLM utility client — free providers only (Groq + Ollama).

Exposes the same interface as the previous paid-API client
so no call-site changes are needed.
"""

from typing import Optional, List, Dict, Any
from ..config import settings
import structlog

logger = structlog.get_logger()


class LLMClient:
    """
    Unified LLM client using free providers.

    Provider priority:
      1. Groq  — cloud, free tier (https://console.groq.com/keys)
      2. Ollama — local, fully free (https://ollama.com)
    """

    def __init__(self, provider: Optional[str] = None):
        # Default to whatever is configured in settings
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.model = settings.DEFAULT_LLM_MODEL
        self._groq = None

    # ------------------------------------------------------------------
    # Lazy client init
    # ------------------------------------------------------------------

    def _get_groq(self):
        if self._groq is None:
            try:
                from groq import Groq  # type: ignore
                if not settings.GROQ_API_KEY:
                    raise ValueError(
                        "GROQ_API_KEY not set. "
                        "Get a free key at https://console.groq.com/keys"
                    )
                self._groq = Groq(api_key=settings.GROQ_API_KEY)
            except ImportError:
                logger.warning("groq package not installed; run: pip install groq")
        return self._groq

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion from a free LLM provider."""
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.provider == "groq":
            return await self._complete_groq(messages, max_tokens, temperature)
        elif self.provider == "ollama":
            return await self._complete_ollama(messages, max_tokens, temperature)
        else:
            # Default to groq, fall back to ollama
            return await self._complete_groq(messages, max_tokens, temperature)

    async def _complete_groq(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Groq cloud inference — free tier."""
        try:
            client = self._get_groq()
            if client is None:
                logger.warning("Groq unavailable, falling back to Ollama")
                return await self._complete_ollama(messages, max_tokens, temperature)

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error("Groq completion failed, trying Ollama", error=str(e))
            return await self._complete_ollama(messages, max_tokens, temperature)

    async def _complete_ollama(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Ollama local inference — fully free, no API key needed."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.post(
                    f"{settings.OLLAMA_ENDPOINT}/api/chat",
                    json={
                        "model": "llama3",   # pulled locally via `ollama pull llama3`
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
                return data.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(
                "Ollama completion failed",
                error=str(e),
                tip="Run `ollama serve` and `ollama pull llama3` to enable local inference.",
            )
            return ""

    # ------------------------------------------------------------------
    # Higher-level helpers (same signatures as before)
    # ------------------------------------------------------------------

    async def extract_entities(self, text: str) -> List[str]:
        """Extract scientific entities from text."""
        prompt = (
            "Extract all scientific entities (concepts, methods, chemicals, genes, etc.) "
            f"from this text. Return them as a comma-separated list:\n\n{text}"
        )
        result = await self.complete(prompt, temperature=0.1, max_tokens=200)
        return [e.strip() for e in result.split(",") if e.strip()]

    async def detect_contradiction(
        self, finding_a: str, finding_b: str
    ) -> Dict[str, Any]:
        """Check if two findings contradict each other."""
        prompt = (
            "Determine if these two scientific findings contradict each other:\n\n"
            f"Finding A: {finding_a}\n\nFinding B: {finding_b}\n\n"
            'Respond with JSON: {"contradicts": bool, "explanation": str, "confidence": float}'
        )
        result = await self.complete(prompt, temperature=0.1, max_tokens=300)
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"contradicts": False, "explanation": "Parse failed", "confidence": 0.0}

    async def summarize_paper(self, title: str, abstract: str) -> str:
        """Generate a concise summary of a paper."""
        prompt = (
            "Summarize this scientific paper in 2-3 sentences:\n\n"
            f"Title: {title}\n\nAbstract: {abstract}"
        )
        return await self.complete(prompt, temperature=0.3, max_tokens=200)

    async def generate_hypothesis(
        self, concepts: List[str], context: str = ""
    ) -> Dict[str, Any]:
        """Generate a hypothesis connecting given concepts."""
        prompt = (
            f"Generate a novel scientific hypothesis connecting these concepts: {', '.join(concepts)}.\n"
            f"Context: {context}\n\n"
            'Respond with JSON: {"hypothesis": str, "confidence": float, "mechanism": str, "experiments": [str]}'
        )
        result = await self.complete(prompt, temperature=0.8, max_tokens=500)
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"hypothesis": result, "confidence": 0.5, "mechanism": "", "experiments": []}


# Singleton — uses provider from settings (default: groq)
llm_client = LLMClient()
