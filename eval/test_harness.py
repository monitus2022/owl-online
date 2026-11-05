"""Eval harness tests: metric math, slices and judge parsing, no network.

Lives in eval/ so the documented gate `pytest eval/` collects it.
"""

from app.pipeline.generate import ABSTAIN_MESSAGE, AskResult
from app.pipeline.retrieve.retriever import RetrievalTrace
from app.schemas import Chunk, ChunkMetadata
from eval.harness import (
    CachedLlm,
    DiagnosticScore,
    GoldItem,
    JudgeVerdict,
    abstention_metrics,
    abstention_metrics_by_slice,
    corpus_vocabulary,
    exact_match,
    judge_sample,
    load_gold,
    normalize_answer,
    novel_entities,
    parse_faithful,
    parse_verdict,
    retrieval_diagnostics_all,
    retrieval_metrics,
    retrieval_metrics_all,
    retrieval_metrics_by_slice,
    sample_answerable,
    summarize_diagnostics,
    summarize_generation,
    summarize_novelty,
    token_f1,
)
from eval.harness.retrieval import _neighbor_hit


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
        self.top_k_seen: list[int] = []

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.top_k_seen.append(top_k)
        return [_chunk(cid) for cid in self._mapping.get(query, [])[:top_k]]


class _Llm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return "an answer [c1]"


class _DiagnosingRetriever:
    def __init__(self, traces: dict[str, RetrievalTrace]) -> None:
        self._traces = traces

    async def diagnose(self, query: str, top_k: int) -> RetrievalTrace:
        return self._traces[query]


async def test_retrieval_diagnostics_split_each_stage():
    items = [
        GoldItem("q1", "q1", True, ["a", "b"], ("simple",)),
        GoldItem("q2", "q2", True, ["c"], ("named_reference",)),
    ]
    traces = {
        "q1": RetrievalTrace(("a",), ("x",), ("a", "x"), ("x",)),
        "q2": RetrievalTrace(("c",), ("c",), ("c",), ("c",)),
    }
    overall, by_slice = await retrieval_diagnostics_all(
        _DiagnosingRetriever(traces), items, k=5
    )
    assert overall.n == 2
    assert overall.dense_hit_n == 2
    assert overall.sparse_hit_n == 1
    assert overall.pool_hit_n == 2
    assert overall.result_hit_n == 1
    assert overall.neighbor_hit_n == 0
    assert abs(overall.dense_recall_at_pool - 0.75) < 1e-9
    assert abs(overall.pool_recall_at_pool - 0.75) < 1e-9
    assert overall.rerank_lift == 0.5
    assert set(by_slice) == {"simple", "named_reference"}


def test_neighbor_hit_marks_an_adjacent_chunk():
    score = DiagnosticScore(
        item_id="q1",
        slice_name="simple",
        dense_recall=0.0,
        sparse_recall=0.0,
        pool_recall=0.0,
        pool_hit=False,
        result_hit=False,
        neighbor_hit=True,
    )
    metrics = summarize_diagnostics([score])
    assert metrics.neighbor_hit_n == 1
    assert metrics.neighbor_hit_rate == 1.0


def test_neighbor_hit_detects_the_same_chapter_adjacent_chunk():
    assert _neighbor_hit({"b1-c01-0010"}, ("b1-c01-0011",))
    assert not _neighbor_hit({"b1-c01-0010"}, ("b1-c02-0011",))
    assert not _neighbor_hit({"b1-c01-0010"}, ("b1-c01-0012",))


async def test_cached_llm_variant_separates_cache_keys(tmp_path):
    zero = CachedLlm(_Llm(), "model", tmp_path, variant="temperature=0")
    warm = CachedLlm(_Llm(), "model", tmp_path, variant="temperature=1")
    await zero.generate("system", "prompt")
    await warm.generate("system", "prompt")
    assert len(list(tmp_path.glob("*.txt"))) == 2
    assert zero.get_cached("system", "prompt") == "an answer [c1]"
    assert zero.get_cached("system", "other") is None
    assert zero.get_cached("system", "prompt", context="ctx") is None


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


async def test_retrieval_metrics_by_slice_groups_without_a_second_pass():
    items = [
        GoldItem("s1", "a", True, ["c1"], ("simple",)),
        GoldItem("n1", "b", True, ["c2"], ("named_reference",)),
    ]
    retriever = _Retriever({"a": ["c1"], "b": ["x"]})
    metrics = await retrieval_metrics_by_slice(retriever, items, k=5)
    assert metrics["simple"].hit_at_k == 1.0
    assert metrics["named_reference"].hit_at_k == 0.0
    # One retrieval per answerable item, not one per slice.
    assert retriever.top_k_seen == [5, 5]


async def test_retrieval_metrics_all_returns_overall_and_slices_in_one_pass():
    items = [
        GoldItem("s1", "a", True, ["c1"], ("simple",)),
        GoldItem("n1", "b", True, ["c2"], ("named_reference",)),
    ]
    retriever = _Retriever({"a": ["c1"], "b": ["c2"]})
    overall, by_slice = await retrieval_metrics_all(retriever, items, k=5)
    assert overall.n == 2
    assert overall.hit_at_k == 1.0
    assert set(by_slice) == {"simple", "named_reference"}
    assert retriever.top_k_seen == [5, 5]


async def test_abstention_metrics_counts_refusals_and_forwards_top_k():
    retriever = _Retriever({})
    metrics = await abstention_metrics(
        retriever, _Llm(), [GoldItem("u1", "z", False, [])], top_k=3
    )
    assert metrics.n == 1
    assert metrics.refused == 1
    assert metrics.rate == 1.0
    assert retriever.top_k_seen == [3]


async def test_abstention_metrics_by_slice():
    items = [
        GoldItem("u1", "z", False, [], ("near_miss_unanswerable",)),
        GoldItem("u2", "w", False, [], ("off_topic",)),
    ]
    metrics = await abstention_metrics_by_slice(_Retriever({}), _Llm(), items, top_k=3)
    assert metrics["near_miss_unanswerable"].refused == 1
    assert metrics["off_topic"].refused == 1


async def test_abstention_forwards_the_retry_budget(monkeypatch):
    seen: dict[str, int] = {}

    async def fake_ask(question, *, retriever, llm, top_k, max_retries):
        seen["max_retries"] = max_retries
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=[],
            attempts=0,
            abstain_reason="no_evidence",
        )

    monkeypatch.setattr("eval.harness.abstention.ask", fake_ask)
    await abstention_metrics(
        _Retriever({}), _Llm(), [GoldItem("u1", "z", False, [])], max_retries=0
    )
    assert seen["max_retries"] == 0


async def test_judge_sample_forwards_the_retry_budget(monkeypatch):
    seen: dict[str, int] = {}

    async def fake_ask(question, *, retriever, llm, top_k, max_retries):
        seen["max_retries"] = max_retries
        return AskResult("an answer [c1]", ["c1"], chunks=[_chunk("c1")])

    class _Judge:
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            return '{"correctness": "correct", "grounded": true}'

    monkeypatch.setattr("eval.harness.judging.ask", fake_ask)
    items = [GoldItem("q1", "q", True, ["c1"], ("simple",))]
    await judge_sample(
        _Retriever({"q": ["c1"]}), _Llm(), _Judge(), items, sample=1, max_retries=0
    )
    assert seen["max_retries"] == 0


def test_parse_verdict_tolerates_prose():
    assert parse_verdict('Sure: {"correctness": "partial", "grounded": true} done') == (
        "partial",
        True,
    )
    assert parse_verdict("no json here") is None
    assert parse_verdict('{"correctness": "amazing", "grounded": 1}') is None


def test_parse_verdict_normalizes_string_booleans():
    assert parse_verdict('{"correctness": "correct", "grounded": "false"}') == (
        "correct",
        False,
    )


def test_parse_verdict_uses_the_first_object():
    raw = '{"correctness": "wrong", "grounded": false} {"correctness": "correct"}'
    assert parse_verdict(raw) == ("wrong", False)


def test_parse_faithful():
    assert parse_faithful('{"faithful": true}') is True
    assert parse_faithful('Sure: {"faithful": "false"}') is False
    assert parse_faithful("no json here") is None
    assert parse_faithful('{"correctness": "correct"}') is None


def test_normalize_answer_strips_articles_and_punctuation():
    assert normalize_answer("The Elder Wand!") == "elder wand"
    assert normalize_answer("  A   Hippogriff. ") == "hippogriff"


def test_citations_do_not_count_as_answer_tokens():
    assert normalize_answer("Fluffy. [b1-c11-0041]") == "fluffy"
    assert exact_match("Fluffy. [b1-c11-0041]", "Fluffy.") == 1.0
    assert token_f1("Fluffy. [b1-c11-0041]", "Fluffy.") == 1.0


def test_exact_match_and_token_f1():
    assert exact_match("The Elder Wand", "Elder Wand") == 1.0
    assert exact_match("Elder Wand", "Resurrection Stone") == 0.0
    assert token_f1("The Elder Wand", "Elder Wand") == 1.0
    assert token_f1("Elder Wand", "Resurrection Stone") == 0.0
    partial = token_f1("Minerva McGonagall", "Professor Minerva McGonagall")
    assert 0.0 < partial < 1.0


def test_summarize_generation_counts_abstentions_and_faithfulness():
    verdicts = [
        JudgeVerdict("a", "correct", True, False, faithful=True, em=1.0, f1=1.0),
        JudgeVerdict(
            "b",
            "wrong",
            False,
            False,
            faithful=False,
            em=0.0,
            f1=0.5,
            judge_parse_failed=True,
            faithful_parse_failed=True,
        ),
        JudgeVerdict("c", "abstained", False, True, faithful=None, em=0.0, f1=0.0),
    ]
    metrics = summarize_generation(verdicts)
    assert metrics.n == 3
    assert metrics.answered == 2
    assert metrics.abstained == 1
    assert abs(metrics.em - (1.0 / 3.0)) < 1e-9
    assert abs(metrics.f1 - (1.5 / 3.0)) < 1e-9
    assert metrics.correct == 1
    assert metrics.wrong == 1
    assert metrics.faithfulness_n == 2
    assert metrics.faithful == 1
    assert metrics.faithfulness_rate == 0.5
    assert metrics.judge_correct_rate == 0.5
    assert metrics.judge_parse_failures == 1
    assert metrics.faithful_parse_failures == 1


def test_sample_answerable_round_robins_slices():
    items = [
        GoldItem(f"s{i}", "q", True, ["c"], ("simple",)) for i in range(3)
    ] + [
        GoldItem(f"n{i}", "q", True, ["c"], ("named_reference",)) for i in range(3)
    ]
    picked = sample_answerable(items, 4)
    assert [item.primary_slice for item in picked] == [
        "simple",
        "named_reference",
        "simple",
        "named_reference",
    ]


def test_load_gold_reads_records(tmp_path):
    path = tmp_path / "g.jsonl"
    path.write_text(
        '{"id": "q1", "question": "x", "answerable": true, '
        '"expected_chunk_ids": ["c1"], "slices": ["simple"], '
        '"reference_answer": "y"}\n'
    )
    items = load_gold(path)
    assert items[0].id == "q1"
    assert items[0].expected_chunk_ids == ["c1"]
    assert items[0].primary_slice == "simple"
    assert items[0].reference_answer == "y"

def test_novel_entity_flags_an_invented_name():
    vocabulary = {"rowena", "ravenclaw", "diadem"}
    assert novel_entities("Herbrand Ravenclaw's diadem.", vocabulary) == ["Herbrand"]


def test_novel_entity_passes_corpus_names_and_aliases():
    vocabulary = {"rowena", "ravenclaw", "voldemort", "riddle", "tom"}
    assert novel_entities("Rowena Ravenclaw, Tom Riddle, Voldemort.", vocabulary) == []


def test_novel_entity_ignores_citation_ids():
    assert novel_entities("Rowan [b9-c99-0000].", {"rowan"}) == []


def test_corpus_vocabulary_is_case_insensitive():
    chunk = Chunk(
        id="c1",
        text="Rowena Ravenclaw",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="B", chapter_name="C"
        ),
    )
    assert corpus_vocabulary([chunk]) == {"rowena", "ravenclaw"}


def test_summarize_novelty_counts_flagged_answers():
    metrics = summarize_novelty(["Rowan.", "Herbrand.", "Herbrand again."], {"rowan"})
    assert metrics.flagged == 2
    assert metrics.n == 3
    assert abs(metrics.rate - 2 / 3) < 1e-9
    assert metrics.tokens == ("Herbrand",)


def test_novel_entity_keeps_a_hyphenated_name_together():
    vocabulary = {"the", "time-turner"}
    assert novel_entities("The Time-Turner.", vocabulary) == []
    assert novel_entities("The Time-Turner and Herbrand.", vocabulary) == ["Herbrand"]
