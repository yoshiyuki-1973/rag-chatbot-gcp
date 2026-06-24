import time
from google import genai
from google.genai import errors


class EmbeddingBatchClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-004",
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
        self.model = model

    def embed_many(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = None
            for attempt in range(1, 4):
                try:
                    response = self.client.models.embed_content(
                        model=self.model,
                        contents=batch,
                    )
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** (attempt - 1))
            embeddings.extend(item.values for item in response.embeddings)
        return embeddings
