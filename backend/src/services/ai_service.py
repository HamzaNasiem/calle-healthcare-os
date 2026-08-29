import httpx
from typing import List, Dict, Any, Optional
from ..core.resilience import CircuitBreaker
from ..core.config import settings

# Share a single circuit breaker across OpenRouter AI service calls
ai_breaker = CircuitBreaker("OpenRouter", failure_threshold=5, recovery_timeout_seconds=60.0)

class AIService:
    def __init__(self):
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": settings.DASHBOARD_URL,
            "X-Title": "Bytelytic OS",
            "Content-Type": "application/json"
        }
        self.backup_headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY_BACKUP}",
            "HTTP-Referer": settings.DASHBOARD_URL,
            "X-Title": "Bytelytic OS",
            "Content-Type": "application/json"
        } if settings.OPENROUTER_API_KEY_BACKUP else None
        
        # Primary models for fast/cheap extraction (updated June 2025)
        self.fallback_chain = [
            "openrouter/free",
            "openai/gpt-4o-mini",
            "anthropic/claude-3-haiku"
        ]

    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 500, temperature: float = 0.2) -> str:
        """
        Sends a chat completion request with built-in fallback across multiple models
        and an optional backup API key to ensure 99.9% uptime.
        """
        async def _execute_chat():
            for model in self.fallback_chain:
                result = await self._attempt(model, messages, max_tokens, temperature, use_backup=False)
                if result:
                    return result
                
                if self.backup_headers:
                    result = await self._attempt(model, messages, max_tokens, temperature, use_backup=True)
                    if result:
                        return result
                    
            raise Exception("All OpenRouter models and API keys failed.")

        return await ai_breaker.call(_execute_chat)

    async def _attempt(self, model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float, use_backup: bool) -> Optional[str]:
        headers = self.backup_headers if use_backup else self.headers
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[ai_service] Attempt failed for model {model} (backup={use_backup}): {str(e)}")
            return None

ai_service = AIService()
