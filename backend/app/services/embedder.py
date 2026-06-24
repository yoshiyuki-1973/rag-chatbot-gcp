from google import genai


class EmbeddingClient:
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

    async def embed(self, text: str) -> list[float]:
        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=text,
        )
        return response.embeddings[0].values
