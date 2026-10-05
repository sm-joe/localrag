from ollama import Client


class EmbeddingService:
    def __init__(
        self,
        base_url: str,
        model: str,
    ) -> None:
        self.client = Client(host=base_url)
        self.model = model

    def embed(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise ValueError(
                "Cannot generate an embedding for empty text."
            )

        response = self.client.embed(
            model=self.model,
            input=text,
        )

        embeddings = response.embeddings

        if not embeddings:
            raise RuntimeError(
                "Ollama returned no embeddings."
            )

        return embeddings[0]