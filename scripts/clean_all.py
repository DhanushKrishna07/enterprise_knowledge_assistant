#!/usr/bin/env python
# Usage: python scripts/clean_all.py
"""
scripts/clean_all.py — Reset all databases, indexes, and caches, and perform a clean document ingestion.
"""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.service import init_user_table, seed_demo_users
from app.core.config import get_settings
from app.documents.jobs import init_tables
from app.indexing.ingest_service import ingest_directory
from app.observability.trace import init_trace_table


def main():
    settings = get_settings()
    print("==================================================")
    print("ENTERPRISE KNOWLEDGE ASSISTANT - TOTAL CLEAN & RESET")
    print("==================================================")

    # 1. Clear ChromaDB directory
    chroma_dir = Path(settings.chroma_path)
    if chroma_dir.exists():
        print(f"Clearing ChromaDB index at: {chroma_dir}")
        try:
            shutil.rmtree(chroma_dir)
            print("ChromaDB index cleared successfully.")
        except Exception as e:
            print(f"Warning: Failed to delete Chroma DB directory: {e}")
    else:
        print("ChromaDB directory does not exist. Skipping.")

    # 2. Clear BM25 index file
    bm25_file = Path(chroma_dir.parent / "bm25_index.pkl")
    if bm25_file.exists():
        print(f"Clearing BM25 index file: {bm25_file}")
        try:
            bm25_file.unlink()
            print("BM25 index file deleted.")
        except Exception as e:
            print(f"Warning: Failed to delete BM25 file: {e}")
    else:
        print("BM25 index file does not exist. Skipping.")

    # 3. Clear SQLite database tables (except users)
    db_path = settings.sqlite_url.replace("sqlite:///", "")
    print(f"Clearing SQLite logs, history, and feedback from database: {db_path}")
    if Path(db_path).exists():
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()

            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]

            tables_to_clear = [
                "chat_messages",
                "ingestion_runs",
                "ingestion_jobs",
                "request_logs",
                "indexed_documents",
                "feedback",
            ]

            for t in tables_to_clear:
                if t in tables:
                    try:
                        cursor.execute(f"DELETE FROM {t}")
                        print(f"Cleared table '{t}'")
                    except Exception as err:
                        print(f"Warning: Could not clear table '{t}': {err}")

            conn.commit()

            try:
                cursor.execute("VACUUM")
                conn.commit()
            except Exception:
                pass  # VACUUM might fail if in transaction or locked

            conn.close()
            print("SQLite tables cleared.")
        except Exception as e:
            print(f"Error resetting SQLite database: {e}")
    else:
        print("SQLite DB file does not exist yet. Skipping.")

    # 4. Clear RAG Response Cache (except locked SQLite database caches)
    cache_dir = Path(settings.cache_path)
    if cache_dir.exists():
        print(f"Clearing RAG caches at: {cache_dir}")
        for root, dirs, files in os.walk(cache_dir, topdown=False):
            for name in files:
                fpath = Path(root) / name
                try:
                    fpath.unlink()
                except Exception:
                    # Ignore locked files like embeddings cache.db
                    pass
            for name in dirs:
                dpath = Path(root) / name
                try:
                    dpath.rmdir()
                except Exception:
                    pass
        print("Cache folder cleared (locked database caches were preserved).")
    else:
        print("Cache directory does not exist. Skipping.")

    # Re-initialize DB tables (schemas) and seed users
    print("Re-initializing tables...")
    try:
        init_tables()
        init_user_table()
        init_trace_table()
        seed_demo_users()
        print("Database structures re-created successfully.")
    except Exception as e:
        print(f"Warning: SQLite database lock prevented initialization: {e}")
        print("This is normal if the server is actively running. We will proceed.")

    # 5. Re-ingest documents from data/documents/
    docs_dir = Path(settings.documents_path)
    docs_dir.mkdir(parents=True, exist_ok=True)

    print("\nStarting fresh document ingestion...")
    try:
        report = ingest_directory(docs_dir)
        print("\n==================================================")
        print("CLEAN INGESTION COMPLETE")
        print("==================================================")
        print(f"Files processed  : {report.files_seen}")
        print(f"Files added      : {report.files_added}")
        print(f"Chunks created   : {report.chunks_added}")
        print(f"Tables extracted : {report.tables_extracted}")
        print(f"Errors           : {len(report.errors)}")
        for err in report.errors:
            print(f"  - {err}")
    except Exception as e:
        print(f"Ingestion failed: {e}")


if __name__ == "__main__":
    main()
