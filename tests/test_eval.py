"""Mini-eval harness tests: metric math and judge parsing, no network."""

from app.schemas import Chunk, ChunkMetadata
from eval.harness import (
    GoldItem,
    abstention_metrics,
    load_gold,
    parse_verdict,
    retrieval_metrics,
)


def _chunk(chunk_id: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text="text",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
    )


class _Retriever:
    """Returns the ids configured for a query, truncated to top_k."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [_chunk(cid) for cid in self._mapping.get(query, [])[:top_k]]


class _Llm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return "an answer [c1]"


async def test_retrieval_metrics_hit_recall_and_mrr():
    items = [
        GoldItem("q1", "a", True, ["c1"]),
        GoldItem("q2", "b", True, ["c2", "c3"]),
    ]
    retriever = _Retriever({"a": ["c1", "x"], "b": ["x", "c2"]})
    metrics = await retrieval_metrics(retriever, items, k=5)
    assert metrics.n == 2
    assert metrics.hit_at_k == 1.0
    assert metrics.recall_at_k == 0.75  # (1/1 + 1/2) / 2
    assert abs(metrics.mrr - (1.0 + 0.5) / 2) < 1e-9


async def test_retrieval_metrics_miss_is_zero():
    items = [GoldItem("q1", "a", True, ["c1"])]
    metrics = await retrieval_metrics(_Retriever({"a": ["x"]}), items, k=5)
    assert metrics.hit_at_k == 0.0
    assert metrics.mrr == 0.0


async def test_abstention_metrics_counts_refusals():
    items = [GoldItem("u1", "z", False, [])]
    metrics = await abstention_metrics(_Retriever({}), _Llm(), items)
    assert metrics.n == 1
    assert metrics.refused == 1
    assert metrics.rate == 1.0


def test_parse_verdict_tolerates_surrounding_prose():
    assert parse_verdict('Sure: {"correctness": "partial", "grounded": true} done') == (
        "partial",
        True,
    )
    assert parse_verdict("no json here") == ("wrong", False)
    assert parse_verdict('{"correctness": "amazing", "grounded": 1}') == ("wrong", True)


def test_load_gold_reads_records(tmp_path):
    path = tmp_path / "g.jsonl"
    path.write_text(
        '{"id": "q1", "question": "x", "answerable": true, "expected_chunk_ids": ["c1"]}\n'
    )
    items = load_gold(path)
    assert items[0].id == "q1"
    assert items[0].expected_chunk_ids == ["c1"]
