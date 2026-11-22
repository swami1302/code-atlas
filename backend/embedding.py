from google import genai
from google.genai import types

from config import settings

# Turns text into vectors with Google's Gemini embedding API. The only module that
# talks to the embedding provider, so a local model can sit beside it later.

MODEL = "gemini-embedding-2"
# Any size from 128 to 3072 works; the first numbers carry the most meaning
DIMENSIONS = 1536
# Stored in chunk_embeddings.model: a new model or size gets its own rows
MODEL_KEY = f"{MODEL}:{DIMENSIONS}"
# Texts per API request
BATCH_SIZE = 100

# The SDK's own retry: 5 attempts with exponential backoff and jitter on 408, 429,
# 5xx and network errors. Waits start at 10s (default 1s) so they span the free
# tier's per-minute quota (100 texts/min, each text counts): ~10, 20, 40, 60s.
client = genai.Client(
    api_key=settings.gemini_api_key,
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(initial_delay=10, max_delay=60)
    ),
)


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """One vector per text, in the same order. One API request: pass at most
    BATCH_SIZE texts."""
    response = await client.aio.models.embed_content(
        model=MODEL,
        # Each text in its own Content: a plain list of strings is read as one
        # multi-part input and comes back as a single combined vector.
        # gemini-embedding-2 has no task_type setting; this prefix tells it the
        # text is a document to be found (queries get their own prefix, Phase 2).
        contents=[
            types.Content(parts=[types.Part(text=f"title: none | text: {text}")])
            for text in texts
        ],
        config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
    )
    return [embedding.values for embedding in response.embeddings]


if __name__ == "__main__":
    # Self-check, calls the real API: python embedding.py
    import asyncio

    vectors = asyncio.run(embed_documents(["def add(a, b): return a + b", "# Hi"]))
    # Two inputs, two vectors (not one combined)
    assert len(vectors) == 2 and all(len(v) == DIMENSIONS for v in vectors)
    print("embedding: ok")
