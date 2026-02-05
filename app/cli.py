import argparse
import json
import logging
import sys

from app.config import Settings
from app.embeddings.embedder import embed_texts, embed_query
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.storage.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def cmd_index(settings: Settings):
    logger.info("Scanning sources...")
    files = scan_sources(settings.sources, settings.global_ignore)
    logger.info(f"Found {len(files)} markdown files")

    store = VectorStore(settings.persist_directory, settings.collection_name)

    all_chunks = []
    for fi in files:
        chunks = parse_and_chunk(
            fi.path, fi.source_root,
            settings.chunk_size, settings.chunk_overlap,
        )
        all_chunks.extend(chunks)
        logger.info(f"  {fi.relative_path}: {len(chunks)} chunks")

    if not all_chunks:
        logger.info("No chunks to index.")
        return

    logger.info(f"Embedding {len(all_chunks)} chunks...")
    texts = [c.content for c in all_chunks]
    embeddings = embed_texts(texts, settings.embedding_model)

    ids = [c.chunk_id for c in all_chunks]
    metadatas = [c.metadata for c in all_chunks]

    logger.info("Storing in ChromaDB...")
    store.add(ids, texts, embeddings, metadatas)
    logger.info(f"Done. Total chunks in store: {store.count}")


def cmd_search(settings: Settings, query: str, top_k: int | None = None):
    store = VectorStore(settings.persist_directory, settings.collection_name)

    if store.count == 0:
        logger.error("No documents indexed. Run 'index' first.")
        return

    k = top_k or settings.top_k
    logger.info(f"Searching for: {query}")

    qe = embed_query(query, settings.embedding_model)
    results = store.query(qe, n_results=k)

    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"], results["metadatas"], results["distances"])
    ):
        score = 1 - dist  # cosine distance to similarity
        source = meta.get("source_path", "unknown")
        heading = meta.get("heading", "")
        print(f"\n--- Result {i+1} (score: {score:.3f}) ---")
        print(f"Source: {source}")
        if heading:
            print(f"Section: {heading}")
        print(f"\n{doc[:300]}{'...' if len(doc) > 300 else ''}")


def cmd_add_source(settings: Settings, path: str):
    settings.add_source(path)
    settings.save()
    logger.info(f"Added source: {path}")


def cmd_stats(settings: Settings):
    store = VectorStore(settings.persist_directory, settings.collection_name)
    files = scan_sources(settings.sources, settings.global_ignore)
    print(f"Sources configured: {len(settings.sources)}")
    for s in settings.sources:
        print(f"  - {s}")
    print(f"Markdown files found: {len(files)}")
    print(f"Chunks in vector store: {store.count}")
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Active LLM: {settings.active_provider}")


def main():
    parser = argparse.ArgumentParser(description="mdkb - Markdown Knowledge Base CLI")
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("index", help="Index all configured sources")

    sp_search = sub.add_parser("search", help="Semantic search")
    sp_search.add_argument("query", help="Search query")
    sp_search.add_argument("-k", type=int, default=None, help="Number of results")

    sp_add = sub.add_parser("add-source", help="Add a source directory")
    sp_add.add_argument("path", help="Directory path to add")

    sub.add_parser("stats", help="Show index statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    settings = Settings.get(args.config)

    if args.command == "index":
        cmd_index(settings)
    elif args.command == "search":
        cmd_search(settings, args.query, args.k)
    elif args.command == "add-source":
        cmd_add_source(settings, args.path)
    elif args.command == "stats":
        cmd_stats(settings)


if __name__ == "__main__":
    main()
