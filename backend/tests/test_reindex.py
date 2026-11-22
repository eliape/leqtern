import json
from argparse import Namespace

import pytest
from fakes import FakeIndexClient
from pdfs import filler, make_pdf

from leqtern import reindex
from leqtern.index import ChunkIndex, DocSummary
from leqtern.library import Library


def respond(kwargs):
    if kwargs["output_format"] is DocSummary:
        return DocSummary(title="New", kind="textbook", summary="Rebuilt.")
    return ChunkIndex(summary="s", sections=[], entries=[], references=[])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(reindex, "backend_running", lambda: False)
    client = FakeIndexClient(respond)
    monkeypatch.setattr(reindex, "make_client", lambda settings: client)
    return data, Library(data)


async def add(library, name, text):
    doc = await library.add(make_pdf([filler(text)]), name)
    (library.folder(doc.id) / "index.json").write_text('{"old": true}')
    return doc


def save_workspace(data, topics):
    (data / "workspace.json").write_text(json.dumps({"version": 1, "topics": topics}))


def args(*match, all=False):
    return Namespace(match=list(match), list=False, missing=False, all=all)


def index_of(library, doc):
    return json.loads((library.folder(doc.id) / "index.json").read_text())


async def test_skips_documents_only_in_archived_topics_or_none(setup) -> None:
    data, library = setup
    kept = await add(library, "kept.pdf", "one")
    shared = await add(library, "shared.pdf", "two")
    archived = await add(library, "archived.pdf", "three")
    unused = await add(library, "unused.pdf", "four")
    save_workspace(
        data,
        [
            {"id": "a", "docs": [{"serverId": kept.id}, {"serverId": shared.id}]},
            {
                "id": "b",
                "archived": True,
                "docs": [{"serverId": shared.id}, {"serverId": archived.id}],
            },
        ],
    )

    assert await reindex.run(args()) == 0

    assert index_of(library, kept)["title"] == "New"
    assert index_of(library, shared)["title"] == "New"
    assert index_of(library, archived) == {"old": True}
    assert index_of(library, unused) == {"old": True}


async def test_all_includes_archived_documents(setup) -> None:
    data, library = setup
    doc = await add(library, "archived.pdf", "three")
    save_workspace(data, [{"id": "b", "archived": True, "docs": [{"serverId": doc.id}]}])

    assert await reindex.run(args(all=True)) == 0
    assert index_of(library, doc)["complete"] is True


async def test_a_failed_rebuild_keeps_the_old_index(setup, monkeypatch) -> None:
    data, library = setup
    doc = await add(library, "book.pdf", "one")
    save_workspace(data, [{"id": "a", "docs": [{"serverId": doc.id}]}])

    def fail(kwargs):
        raise RuntimeError("overloaded")

    monkeypatch.setattr(reindex, "make_client", lambda settings: FakeIndexClient(fail))
    assert await reindex.run(args("book")) == 1
    assert index_of(library, doc) == {"old": True}
    assert not (library.folder(doc.id) / "index.json.old").exists()
