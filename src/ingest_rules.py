"""
Ingest Income Tax Rules into ChromaDB
======================================
Loads scraped rule markdown files and adds them to the vector database.

This script is designed to ADD rules to the existing ChromaDB that already
contains the Income Tax Act 1961 (from ingest2.py). It uses the same
embedding model and persist directory.

Usage:
    python src/ingest_rules.py              # ingest new rules
    python src/ingest_rules.py --rebuild    # delete old DB and rebuild from scratch
"""

import argparse
import os
import shutil

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ---------------------------------------------------------------------------
# Configuration — matches rag_engine.py and ingest2.py
# ---------------------------------------------------------------------------
RULES_DIR = os.path.join("data", "raw_markdown", "rules")
DB_PATH = os.path.join("data", "chroma_db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def load_rule_documents():
    """Load all scraped rule markdown files."""
    if not os.path.exists(RULES_DIR):
        raise FileNotFoundError(
            f"Rules directory not found: {RULES_DIR}\n"
            "Run 'python scrapers/scrape_all_rules.py' first."
        )

    # Count valid files (skip tiny/broken ones)
    valid_files = [
        f for f in os.listdir(RULES_DIR)
        if f.endswith(".md") and os.path.getsize(os.path.join(RULES_DIR, f)) > 100
    ]
    print(f"  Found {len(valid_files)} valid rule files in {RULES_DIR}")

    # Use TextLoader for .md files — simpler and more reliable than
    # UnstructuredMarkdownLoader for our pre-formatted content
    loader = DirectoryLoader(
        RULES_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()

    # Tag each document with metadata for filtering
    for doc in docs:
        doc.metadata["doc_type"] = "rule"
        # Extract rule number from filename: rule_2BA.md → 2BA
        basename = os.path.basename(doc.metadata.get("source", ""))
        rule_num = basename.replace("rule_", "").replace(".md", "")
        doc.metadata["rule_number"] = rule_num

    print(f"  Loaded {len(docs)} documents")
    return docs


def chunk_documents(docs):
    """Split rule documents into chunks optimized for legal text retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        separators=[
            "\n# ",         # Rule headers
            "\n## ",        # Sub-sections
            "\n### ",       # Sub-sub-sections
            "\n---",        # Horizontal rules (our metadata separator)
            "\n\n",         # Paragraphs
            "\n",           # Lines
            " ",            # Words
        ],
    )
    chunks = splitter.split_documents(docs)
    print(f"  Created {len(chunks)} chunks")
    return chunks


def ingest_rules(rebuild=False):
    """Main ingestion pipeline."""
    print("=" * 50)
    print("  Income Tax Rules — Vector DB Ingestion")
    print("=" * 50)

    # Optional: rebuild entire DB
    if rebuild and os.path.exists(DB_PATH):
        print(f"\n  Deleting existing DB at {DB_PATH} ...")
        shutil.rmtree(DB_PATH)

    # 1. Load
    print("\n--- Loading rule documents ---")
    docs = load_rule_documents()

    if not docs:
        print("  No documents to ingest. Exiting.")
        return

    # 2. Chunk
    print("\n--- Splitting into chunks ---")
    chunks = chunk_documents(docs)

    # 3. Embed & store
    print("\n--- Generating embeddings and storing in ChromaDB ---")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    print(f"  Database path:   {DB_PATH}")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH,
    )

    # Verify
    count = vector_db._collection.count()
    print(f"\n  Total documents in ChromaDB: {count}")
    print(f"  Rules ingestion complete!")
    print(f"\n  You can now run the app:  streamlit run app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Income Tax Rules into ChromaDB")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Delete existing DB and rebuild from scratch (will need to re-run ingest2.py too)"
    )
    args = parser.parse_args()
    ingest_rules(rebuild=args.rebuild)
