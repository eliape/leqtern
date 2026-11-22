import asyncio
from types import SimpleNamespace

import pytest
from fakes import FakeIndexClient, usage
from pdfs import filler, make_pdf

from leqtern.index import (
    AUTO_RETRIES,
    RETRY_AFTER_SECONDS,
    ChunkIndex,
    ChunkRecord,
    DocIndex,
    DocSummary,
    Entry,
    HeadingFix,
    Indexer,
    Section,
    apply_heading_fixes,
    chunk_ranges,
    clamp_chunk,
    match_capitals,
    merge_entries,
    merge_sections,
    render_outline,
)
from leqtern.library import Library
from leqtern.usage import UsageLog


def test_splits_documents_into_twenty_page_chunks() -> None:
    assert chunk_ranges(45) == [(1, 20), (21, 40), (41, 45)]
    assert chunk_ranges(3) == [(1, 3)]


def test_joins_sections_that_cross_chunk_boundaries() -> None:
    sections = [
        Section(title="2 Derivatives", level=1, start_page=15, end_page=20, summary="Rates."),
        Section(title="2 Derivatives", level=1, start_page=21, end_page=30, summary="Rules."),
        Section(title="2.1 The chain rule", level=2, start_page=22, end_page=24, summary="Comp."),
    ]
    merged = merge_sections(sections)
    assert [(s.title, s.start_page, s.end_page) for s in merged] == [
        ("2 Derivatives", 15, 30),
        ("2.1 The chain rule", 22, 24),
    ]
    assert merged[0].summary == "Rates. Rules."


def test_orders_sections_by_where_their_headings_are() -> None:
    sections = [
        Section(title="3 Tensors", level=1, start_page=13, end_page=13, top=0.4, summary=""),
        Section(title="2.5 Regions", level=2, start_page=13, end_page=13, top=0.05, summary=""),
        Section(title="2 Lorentz", level=1, start_page=5, end_page=12, summary=""),
    ]
    merged = merge_sections(sections, page_count=30)
    assert [(s.title, s.end_page) for s in merged] == [
        ("2 Lorentz", 13),
        ("2.5 Regions", 13),
        ("3 Tensors", 30),
    ]


def test_drops_headings_marked_as_continued() -> None:
    sections = [
        Section(title="Exercises III", level=2, start_page=40, end_page=40, summary=""),
        Section(title="Exercises III (continued)", level=1, start_page=41, end_page=42, summary=""),
        Section(title="Continued fractions", level=2, start_page=43, end_page=44, summary=""),
    ]
    assert [s.title for s in merge_sections(sections)] == ["Exercises III", "Continued fractions"]


def test_drops_single_exercises_and_running_headers() -> None:
    def sec(title: str, level: int, page: int) -> Section:
        return Section(title=title, level=level, start_page=page, end_page=page, summary="")

    sections = [
        sec("3 Solutions", 1, 50),
        sec("3.1 Solutions to Problems in Special Relativity Theory", 2, 50),
        sec("3.1 Solutions to Problems in Special Relativity Theory", 2, 52),
        sec("Problem 1.12", 3, 51),
        sec("3.2 Solutions to Problems in General Relativity Theory", 2, 60),
        sec("2.47", 3, 61),
        sec("Problem 2.48: Geodesics", 3, 62),
        sec("3.2 Solutions to Problems in General Relativity Theory", 2, 63),
        sec("Exercises", 2, 64),
        sec("4 Cosmology", 1, 70),
        sec("Exercises", 2, 80),
    ]
    assert [(s.title, s.start_page) for s in merge_sections(sections)] == [
        ("3 Solutions", 50),
        ("3.1 Solutions to Problems in Special Relativity Theory", 50),
        ("3.2 Solutions to Problems in General Relativity Theory", 60),
        ("Exercises", 64),
        ("4 Cosmology", 70),
        ("Exercises", 80),
    ]


def test_keeps_problems_that_are_the_top_level() -> None:
    sections = [
        Section(title=f"Problem {n}", level=1, start_page=n, end_page=n, summary="")
        for n in (1, 2, 3)
    ]
    assert len(merge_sections(sections)) == 3


def test_capitalises_a_lower_case_heading_like_the_others() -> None:
    sections = [
        Section(title=t, level=1, start_page=n, end_page=n, summary="")
        for n, t in enumerate(
            [
                "1 Special Relativity",
                "2 Tensor Algebra",
                "3 the theory of gravitation",
                "4 Black Holes",
            ]
        )
    ]
    sections.append(Section(title="4.1 the horizon", level=2, start_page=9, end_page=9, summary=""))
    match_capitals(sections)
    assert sections[2].title == "3 The Theory of Gravitation"
    assert sections[4].title == "4.1 the horizon"  # nothing to compare it with


def test_applies_heading_fixes_from_the_summary() -> None:
    sections = [
        Section(title="III. Relativistic Optics", level=1, start_page=1, end_page=1, summary=""),
        Section(title="IV SPACETIME", level=1, start_page=2, end_page=2, summary=""),
        Section(title="Exercises IV", level=1, start_page=3, end_page=3, summary=""),
    ]
    apply_heading_fixes(
        sections,
        [
            HeadingFix(title="IV SPACETIME", new_title="IV. Spacetime", level=1),
            HeadingFix(title="exercises iv", new_title="Exercises IV", level=2),
        ],
    )
    assert [(s.title, s.level) for s in sections] == [
        ("III. Relativistic Optics", 1),
        ("IV. Spacetime", 1),
        ("Exercises IV", 2),
    ]


def test_merges_entries_by_kind_and_name() -> None:
    entries = [
        Entry(kind="term", name="Derivative", description="d", pages=[12]),
        Entry(kind="term", name="derivative", description="d", pages=[30, 12]),
        Entry(kind="figure", name="Figure 2", description="f", pages=[13]),
    ]
    merged = merge_entries(entries)
    assert [(e.kind, e.pages) for e in merged] == [("term", [12, 30]), ("figure", [13])]


def test_keeps_page_numbers_inside_the_chunk() -> None:
    chunk = ChunkIndex(
        summary="s",
        sections=[Section(title="A", level=7, start_page=19, end_page=99, summary="")],
        entries=[Entry(kind="term", name="x", description="", pages=[0, 25])],
        references=[],
    )
    clamped = clamp_chunk(chunk, 21, 40)
    assert (clamped.sections[0].start_page, clamped.sections[0].end_page) == (21, 40)
    assert clamped.sections[0].level == 4
    assert clamped.entries[0].pages == [21, 25]


@pytest.fixture
def library(tmp_path):
    return Library(tmp_path)


async def test_indexes_a_document_with_text_and_scanned_pages(library, tmp_path) -> None:
    pages = [filler(f"topic {n}") for n in range(1, 25)]
    pages[21] = []  # page 22 is "scanned"
    doc = await library.add(make_pdf(pages), "book.pdf")

    def respond(kwargs):
        if kwargs["output_format"] is DocSummary:
            return DocSummary(title="A Book", kind="textbook", summary="About topics.")
        content = kwargs["messages"][0]["content"]
        start = 1 if any("PDF page 1 " in b.get("text", "") for b in content) else 21
        return ChunkIndex(
            summary=f"Pages from {start}.",
            sections=[
                Section(
                    title=f"Part {start}",
                    level=1,
                    start_page=start,
                    end_page=start + 3,
                    summary="s",
                )
            ],
            entries=[Entry(kind="term", name=f"term {start}", description="d", pages=[start])],
            references=[],
        )

    client = FakeIndexClient(respond)
    usage = UsageLog(tmp_path / "usage.jsonl")
    indexer = Indexer(library, usage, lambda: client)
    index = await indexer.index(doc.id)

    assert index.complete and index.title == "A Book" and index.kind == "textbook"
    assert [c.start_page for c in index.chunks] == [1, 21]
    assert index.scanned_pages == [22]
    assert [s.title for s in index.sections] == ["Part 1", "Part 21"]
    # Text pages go as text, the scanned page as an image, all with PDF page headers.
    second = next(r for r in client.requests if "PDF page 21 " in str(r["messages"]))
    kinds = [b["type"] for b in second["messages"][0]["content"]]
    assert kinds.count("image") == 1
    assert client.requests[0]["model"] == "claude-haiku-5-5"
    calls = usage.summary()
    assert calls["index_chunk"]["calls"] == 2
    assert calls["index_chunk"]["image_pages"] == 1
    status = indexer.doc_status(doc.id)
    assert status["status"] == "ready"
    # The title and kind go with it, for the sidebar's card.
    assert (status["title"], status["kind"]) == (index.title, index.kind)
    # Saved: a new indexer finds it without indexing again.
    assert Indexer(library, usage, lambda: None).doc_status(doc.id)["status"] == "ready"
    assert "Part 21 [pp. 21–24]" in render_outline(doc, index)


async def test_reports_a_missing_api_key_as_an_indexing_error(library, tmp_path) -> None:
    doc = await library.add(make_pdf([filler("x")]), "a.pdf")
    indexer = Indexer(library, UsageLog(None), lambda: None)
    indexer.enqueue(doc.id)
    for _ in range(50):
        await asyncio.sleep(0.01)
        if indexer.doc_status(doc.id)["status"] == "error":
            break
    status = indexer.doc_status(doc.id)
    assert status["status"] == "error"
    assert "ANTHROPIC_API_KEY" in status["error"]


async def test_resumes_a_half_indexed_document_after_a_restart(library, tmp_path) -> None:
    doc = await library.add(make_pdf([filler("x")]), "a.pdf")
    # A fresh indexer, as after the backend restarted mid-index: nothing is queued.
    indexer = Indexer(library, UsageLog(None), lambda: None)
    indexer.resume(doc.id)
    assert indexer.doc_status(doc.id)["status"] == "queued"
    for _ in range(50):
        await asyncio.sleep(0.01)
        if indexer.doc_status(doc.id)["status"] == "error":
            break
    # It ran (and failed here for want of a key); asking again does not retry a failure.
    assert indexer.doc_status(doc.id)["status"] == "error"
    indexer.resume(doc.id)
    assert indexer.doc_status(doc.id)["status"] == "error"


async def test_an_index_made_before_kinds_gets_its_kind_and_keeps_its_summary(
    library, tmp_path
) -> None:
    doc = await library.add(make_pdf([filler("x")]), "exam.pdf")

    def respond(kwargs):
        assert kwargs["output_format"] is DocSummary  # no page is indexed again
        return DocSummary(title="New title", kind="exam", summary="New summary.")

    client = FakeIndexClient(respond)
    indexer = Indexer(library, UsageLog(None), lambda: client)
    old = DocIndex(
        doc_id=doc.id,
        title="Exam",
        summary="An exam.",
        page_count=1,
        labels=[None],
        chunks=[ChunkRecord(start_page=1, end_page=1, summary="Q1.")],
        complete=True,
    )
    indexer._save(old)
    indexer.enqueue(doc.id)
    for _ in range(50):
        await asyncio.sleep(0.01)
        if indexer.get(doc.id).kind:
            break
    index = indexer.get(doc.id)
    assert (index.kind, index.title, index.summary) == ("exam", "Exam", "An exam.")
    assert indexer.doc_status(doc.id)["status"] == "ready"
    # Once it has a kind it is not queued again.
    indexer.enqueue(doc.id)
    assert len(client.requests) == 1


async def wait_for_error(indexer: Indexer, doc_id: str) -> None:
    for _ in range(50):
        await asyncio.sleep(0.01)
        if indexer.doc_status(doc_id)["status"] == "error":
            return


async def test_a_failure_is_tried_again_a_few_times_and_whenever_the_reader_asks(
    library, tmp_path
) -> None:
    doc = await library.add(make_pdf([filler("x")]), "a.pdf")
    indexer = Indexer(library, UsageLog(None), lambda: None)
    indexer.enqueue(doc.id)
    await wait_for_error(indexer, doc.id)
    for _ in range(AUTO_RETRIES):
        # As if the failure was a while ago.
        indexer.status[doc.id]["failed_at"] -= RETRY_AFTER_SECONDS
        indexer.resume(doc.id)
        assert indexer.doc_status(doc.id)["status"] == "queued"
        await wait_for_error(indexer, doc.id)
    indexer.status[doc.id]["failed_at"] -= RETRY_AFTER_SECONDS
    indexer.resume(doc.id)
    assert indexer.doc_status(doc.id)["status"] == "error"
    indexer.retry(doc.id)
    assert indexer.doc_status(doc.id)["status"] == "queued"


async def test_a_damaged_index_file_is_indexed_again(library, tmp_path) -> None:
    doc = await library.add(make_pdf([filler("x")]), "a.pdf")
    indexer = Indexer(library, UsageLog(None), lambda: None)
    indexer.index_path(doc.id).write_text('{"doc_id": "')
    assert indexer.get(doc.id) is None
    assert indexer.doc_status(doc.id)["status"] == "queued"


async def test_damaged_pages_are_read_again_from_the_pdf(tmp_path) -> None:
    doc = await Library(tmp_path).add(make_pdf([filler("limits")]), "a.pdf")
    (tmp_path / "docs" / doc.id / "pages.json").write_text('{"id": ')
    again = Library(tmp_path).get(doc.id)
    assert again is not None and "limits" in again.pages[0].text
    assert Library(tmp_path).get("../docs") is None


async def test_deleting_a_document_stops_its_indexing_and_the_worker_goes_on(library) -> None:
    slow = await library.add(make_pdf([filler("slow")]), "slow.pdf")
    next_doc = await library.add(make_pdf([filler("next")]), "next.pdf")
    started = asyncio.Event()

    class Client:
        def __init__(self) -> None:
            self.messages = SimpleNamespace(parse=self.parse)

        async def parse(self, **kwargs):
            if "slow" in str(kwargs["messages"]):
                started.set()
                await asyncio.sleep(30)
            output = (
                DocSummary(title="T", kind="other", summary="S.")
                if kwargs["output_format"] is DocSummary
                else ChunkIndex(summary="s", sections=[], entries=[], references=[])
            )
            return SimpleNamespace(parsed_output=output, usage=usage(), stop_reason="end_turn")

    indexer = Indexer(library, UsageLog(None), lambda: Client())
    indexer.enqueue(slow.id)
    indexer.enqueue(next_doc.id)
    await asyncio.wait_for(started.wait(), 1)
    indexer.forget(slow.id)
    for _ in range(100):
        await asyncio.sleep(0.01)
        if indexer.doc_status(next_doc.id)["status"] == "ready":
            break
    assert indexer.doc_status(next_doc.id)["status"] == "ready"
    assert indexer.get(slow.id) is None or not indexer.get(slow.id).complete
