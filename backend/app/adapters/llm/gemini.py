from google import genai
from google.genai import errors
from google.genai import types

from app.adapters.llm.base import BaseLLMClient


class GeminiLLMClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str | None,
        models: list[str],
        vertexai: bool = False,
        project: str | None = None,
        location: str | None = None,
    ):
        if vertexai:
            self.client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )
        else:
            self.client = genai.Client(
                api_key=api_key,
            )
        self.models = models

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> str:
        last_model = self.models[-1]
        for model in self.models:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    ),
                )
                return response.text or ""
            except errors.ServerError as exc:
                if model == last_model or not self._is_retryable_unavailable(exc):
                    raise
        return ""

    def _is_retryable_unavailable(self, exc: errors.ServerError) -> bool:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return status_code == 503 or "503" in str(exc) or "UNAVAILABLE" in str(exc)
