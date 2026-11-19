"""
Rebuild document indexes from the console, without the server.

    make reindex                      # every document
    make reindex ARGS="--list"        # show the documents and their index state
    make reindex ARGS="calculus"      # documents whose name or id contains "calculus"
    make reindex ARGS="--missing"     # only documents without a finished index
    make reindex ARGS="--all"         # also documents only in archived topics, or in none

Documents that are only in archived topics, or in no topic at all, are skipped unless --all
is given (a document also in an active topic is rebuilt).

Only index.json is replaced; the PDFs and their pages stay. The old index is kept until the
new one is finished, so a failed or interrupted rebuild leaves it as it was. Stop `make dev`
first: the running backend keeps indexes in memory and would index alongside this.
"""

import argparse
import asyncio
import os
import socket
import sys
import time
from pathlib import Path

from .config import get_settings
from .index import Indexer
from .library import DocInfo, Library
from .main import make_client
from .saved import SavedWorkspace
from .usage import UsageLog

BACKEND_PORT = 8000


def backend_running(port: int = BACKEND_PORT) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def all_docs(library: Library) -> list[DocInfo]:
    folder = library.root / "docs"
    if not folder.is_dir():
        return []
    ids = sorted(p.name for p in folder.iterdir() if (p / "source.pdf").is_file())
    docs = [library.get(i) for i in ids]
    return sorted((d for d in docs if d), key=lambda d: d.name.lower())


def topic_use(saved: SavedWorkspace) -> tuple[set[str], set[str], dict[str, str]]:
    """Document ids in active topics, ids in archived ones, and each document's tab name."""
    active: set[str] = set()
    archived: set[str] = set()
    names: dict[str, str] = {}
    workspace = saved.load() or {}
    for topic in workspace.get("topics", []):
        ids = archived if topic.get("archived") else active
        for doc in topic.get("docs", []):
            if server_id := doc.get("serverId"):
                ids.add(server_id)
                names.setdefault(server_id, doc.get("name") or "")
    return active, archived, names


def use(doc: DocInfo, active: set[str], archived: set[str]) -> str:
    if doc.id in active:
        return "active"
    return "archived" if doc.id in archived else "unused"


def state(indexer: Indexer, doc: DocInfo) -> str:
    if not indexer.index_path(doc.id).exists():
        return "no index"
    index = indexer.get(doc.id)
    if index is None:
        return "damaged"
    return "indexed" if index.complete else "partial"


def choose(docs: list[DocInfo], words: list[str]) -> list[DocInfo]:
    if not words:
        return docs
    return [d for d in docs if any(w.lower() in f"{d.name} {d.id}".lower() for w in words)]


def bar(done: int, total: int, width: int = 24) -> str:
    filled = round(width * done / total) if total else width
    return "█" * filled + "░" * (width - filled)


async def rebuild(indexer: Indexer, doc: DocInfo, show: bool) -> float:
    """Index one document from scratch. Returns what it cost in dollars."""
    path = indexer.index_path(doc.id)
    backup = path.with_name("index.json.old")
    if path.exists():
        os.replace(path, backup)
    indexer.forget(doc.id)
    calls_before = len(indexer.usage.calls)
    began = time.monotonic()
    task = asyncio.create_task(indexer.index(doc.id))
    try:
        while not task.done():
            if show:
                done = indexer.status.get(doc.id, {}).get("pages_done", 0)
                seconds = time.monotonic() - began
                line = f"{bar(done, doc.page_count)} {done}/{doc.page_count} pages  {seconds:.0f}s"
                print(f"\r  {line}", end="", flush=True)
            await asyncio.wait({task}, timeout=0.5)
        task.result()
    except BaseException:
        task.cancel()
        # Put the old index back, so a failed rebuild changes nothing.
        if backup.exists():
            os.replace(backup, path)
        else:
            path.unlink(missing_ok=True)
        indexer.forget(doc.id)
        if show:
            print()
        raise
    backup.unlink(missing_ok=True)
    cost = sum(c.cost for c in indexer.usage.calls[calls_before:])
    seconds = time.monotonic() - began
    if show:
        print(f"\r  {bar(1, 1)} {doc.page_count} pages in {seconds:.0f}s, ${cost:.3f}" + " " * 8)
    return cost


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    library = Library(settings.data_dir)
    usage = UsageLog(settings.data_dir / "usage.jsonl")
    indexer = Indexer(library, usage, lambda: make_client(settings))
    docs = all_docs(library)
    active, archived, names = topic_use(SavedWorkspace(settings.data_dir / "workspace.json"))
    for d in docs:
        d.name = names.get(d.id) or d.name
    if not docs:
        print(f"No documents in {Path(settings.data_dir).resolve() / 'docs'}.")
        return 0

    chosen = choose(docs, args.match)
    if args.missing:
        chosen = [d for d in chosen if state(indexer, d) != "indexed"]

    if args.list:
        for d in chosen:
            print(
                f"{d.id}  {use(d, active, archived):8}  {state(indexer, d):8}  "
                f"{d.page_count:5} pp.  {d.name}"
            )
        return 0
    if not args.all:
        skipped = [d for d in chosen if d.id not in active]
        chosen = [d for d in chosen if d.id in active]
        if skipped:
            print(
                f"Skipping {len(skipped)} document{'s' if len(skipped) != 1 else ''} only in "
                "archived topics or in none (--all includes them)."
            )
    if not chosen:
        print("No documents match." if args.match else "Every document is already indexed.")
        return 1 if args.match else 0
    if make_client(settings) is None:
        print("No API key: add ANTHROPIC_API_KEY to backend/.env.", file=sys.stderr)
        return 1
    if backend_running():
        print(
            f"The backend is running on port {BACKEND_PORT}. Stop `make dev` first: it keeps "
            "indexes in memory and would index the same documents alongside this.",
            file=sys.stderr,
        )
        return 1

    pages = sum(d.page_count for d in chosen)
    print(f"Rebuilding {len(chosen)} index{'es' if len(chosen) != 1 else ''} ({pages} pages).")
    show = sys.stdout.isatty()
    total, failed = 0.0, []
    for n, doc in enumerate(chosen, 1):
        print(f"[{n}/{len(chosen)}] {doc.name}  ({doc.id})")
        try:
            total += await rebuild(indexer, doc, show)
        except Exception as error:
            failed.append(doc)
            print(f"  Failed, kept the old index: {error or type(error).__name__}")
    print(f"Done: {len(chosen) - len(failed)} rebuilt, {len(failed)} failed, ${total:.3f}.")
    if not failed:
        print("Start `make dev` and reload the page to use the new indexes.")
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="make reindex",
        description="Rebuild document indexes (index.json only; PDFs are kept).",
    )
    parser.add_argument("match", nargs="*", help="only documents whose name or id contains this")
    parser.add_argument("--list", action="store_true", help="list documents and stop")
    parser.add_argument(
        "--all", action="store_true", help="also documents only in archived topics, or in none"
    )
    parser.add_argument(
        "--missing", action="store_true", help="only documents without a finished index"
    )
    try:
        sys.exit(asyncio.run(run(parser.parse_args())))
    except KeyboardInterrupt:
        print("\nStopped. The interrupted document keeps its old index.")
        sys.exit(130)


if __name__ == "__main__":
    main()
