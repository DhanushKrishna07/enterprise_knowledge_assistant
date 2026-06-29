#!/usr/bin/env python
# Usage: python scripts/clear_cache.py
#
# To INSPECT cache contents directly via sqlite3 CLI before clearing
# (DiskCache stores entries in a SQLite DB at <cache_path>/rag/cache.db):
#
#   -- List all cache keys and their sizes:
#   sqlite3 <cache_path>/rag/cache.db \
#     "SELECT key, size, datetime(store_time, 'unixepoch', 'localtime') AS stored_at, \
#             datetime(expire_time, 'unixepoch', 'localtime') AS expires_at \
#      FROM Cache ORDER BY store_time DESC;"
#
#   -- Count entries by type (query_answer / response / retrieval):
#   sqlite3 <cache_path>/rag/cache.db \
#     "SELECT SUBSTR(key, 1, INSTR(key, '::')-1) AS entry_type, COUNT(*) AS total \
#      FROM Cache GROUP BY entry_type;"
#
#   NOTE: The 'value' column is pickle-encoded binary — use _show_cache_contents()
#         below (or run this script) to print human-readable question/answer pairs.

"""Clear RAG response and retrieval caches (does not touch indexes or DB).

Preferred: calls POST /admin/cache/clear on the running server so the
live in-process cache is cleared immediately.

Fallback: opens the diskcache directly when the server is not running.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

BASE_URL = "http://127.0.0.1:8000"
# Demo admin credentials — change if you have a different admin account.
ADMIN_EMAIL = "admin@nimbuscloud.com"
ADMIN_PASSWORD = "admin1234"


def _login() -> str | None:
    """Return a JWT token for the admin user, or None on failure."""
    try:
        body = json.dumps({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/auth/login",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp).get("access_token")
    except Exception:
        return None


def _clear_via_server(token: str) -> bool:
    """Call the live server's cache-clear endpoint. Returns True on success."""
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/admin/cache/clear",
            data=b"",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.load(resp)
        if result.get("status") == "ok":
            print(f"Cache cleared via server ({result.get('entries_cleared', '?')} entries removed).")
            return True
        print(f"Server reported: {result}")
        return False
    except Exception as exc:
        print(f"Server cache-clear request failed: {exc}")
        return False


def _show_cache_contents() -> None:
    """Print all Q&A entries stored in the DiskCache before clearing."""
    settings = get_settings()
    try:
        import diskcache  # type: ignore[import]
        import pickle

        cache_path = f"{settings.cache_path}/rag"
        with diskcache.Cache(cache_path) as cache:
            total = len(cache)
            if total == 0:
                print("Cache is empty — nothing to preview.")
                return

            print(f"\n{'='*70}")
            print(f"  CACHE PREVIEW  ({total} total entries in {cache_path})")
            print(f"{'='*70}")

            counts = {"query_answer": 0, "response": 0, "retrieval": 0, "other": 0}
            qa_entries: list[dict] = []

            for key in cache.iterkeys():
                # Determine entry type from key prefix
                if key.startswith("query_answer::"):
                    counts["query_answer"] += 1
                    entry_type = "QUERY ANSWER"
                elif key.startswith("response::"):
                    counts["response"] += 1
                    entry_type = "RESPONSE"
                elif key.startswith("retrieval::"):
                    counts["retrieval"] += 1
                    continue  # retrieval entries hold chunk lists, skip verbose print
                else:
                    counts["other"] += 1
                    entry_type = "OTHER"

                try:
                    value = cache.get(key)
                    if isinstance(value, dict):
                        qa_entries.append({"type": entry_type, "key": key, "data": value})
                except Exception:
                    pass  # skip unreadable entries

            # Summary counts
            print(f"  query_answer entries : {counts['query_answer']}")
            print(f"  response     entries : {counts['response']}")
            print(f"  retrieval    entries : {counts['retrieval']}  (skipped — raw chunk lists)")
            if counts["other"]:
                print(f"  other        entries : {counts['other']}")
            print(f"{'='*70}")

            if not qa_entries:
                print("  No readable Q&A entries found.")
            else:
                for i, entry in enumerate(qa_entries, 1):
                    d = entry["data"]
                    q = d.get("rewritten_query") or d.get("query", "(unknown)")
                    a = d.get("answer", "(no answer field)")
                    confidence = d.get("confidence", "N/A")
                    answerability = d.get("answerability", "N/A")
                    model = d.get("prompt_version", "N/A")

                    # Truncate long answers for readability
                    a_preview = (a[:200] + "...") if len(a) > 200 else a

                    print(f"\n  [{i}] {entry['type']}")
                    print(f"      Question    : {q}")
                    print(f"      Answer      : {a_preview}")
                    print(f"      Confidence  : {confidence}")
                    print(f"      Answerability: {answerability}")
                    print(f"      Prompt ver  : {model}")
                    print(f"      Cache key   : {entry['key'][:60]}...")

            print(f"\n{'='*70}\n")

    except ImportError:
        print("diskcache not installed; cannot preview cache contents.")
    except Exception as exc:
        print(f"Cache preview failed: {exc}")


def _clear_directly() -> None:
    """Fallback: open the diskcache directly (only safe when server is stopped)."""
    settings = get_settings()
    try:
        import diskcache  # type: ignore[import]

        cache_path = f"{settings.cache_path}/rag"
        with diskcache.Cache(cache_path) as cache:
            count = len(cache)
            cache.clear()
        print(f"Cache cleared directly ({count} entries removed from {cache_path}).")
    except ImportError:
        print("diskcache not installed; nothing to clear.")
    except Exception as exc:
        print(f"Direct cache clear failed: {exc}")


def main() -> None:
    # Show all stored Q&A entries before clearing so you know what will be lost.
    _show_cache_contents()

    # Try server-side clear first (correct when server is running).
    token = _login()
    if token:
        if _clear_via_server(token):
            print("Cache clear complete.")
            return
        print("Falling back to direct clear...")
    else:
        print("Server not reachable — clearing cache directly (server must be stopped).")

    _clear_directly()
    print("Cache clear complete.")


if __name__ == "__main__":
    main()
