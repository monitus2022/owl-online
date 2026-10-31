# Create fake entities for testing, repeated usage
from collections.abc import AsyncIterator

from app.schemas import Chunk, ChunkMetadata

# Fake contract classes


class FakeEmbedder:
    async def embed(self, texts):
        return [[0.0] * 100] * len(texts)


class FakeReranker:
    async def rerank(self, query, chunks, top_k):
        return chunks[:top_k]


class FakeRetriever:
    async def retrieve(self, query, top_k):
        return [
            Chunk(
                id=str(i),
                text=f"Chunk {i}",
                metadata=ChunkMetadata(
                    book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
                ),
            )
            for i in range(top_k)
        ]


class FakeLlm:
    async def generate(self, system, prompt, context=None):
        return "Hello World!"

    def stream(self, system, prompt, context=None) -> AsyncIterator[str]:
        # Not using normal iterator as output since Async
        async def gen():
            for t in ("Hello", " ", "World", "!"):
                yield t

        return gen()
