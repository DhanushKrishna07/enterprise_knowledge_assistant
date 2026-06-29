# Usage: python scripts/delete_last_trace.py

"""Delete the most recent request_log entry (to remove a slow/outlier query)."""
import sqlite3

DB = "data/app.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, question, latency_ms, created_at FROM request_logs ORDER BY created_at DESC LIMIT 5"
).fetchall()
print("=== Last 5 traces ===")
for r in rows:
    q = (r["question"] or "")[:60]
    print(f"  [{r['created_at']}] {r['latency_ms']}ms | {q}")

last = conn.execute(
    "SELECT id, question FROM request_logs ORDER BY created_at DESC LIMIT 1"
).fetchone()
if last:
    q = (last["question"] or "")[:80]
    print(f"\nDeleting latest record: {q}")
    conn.execute("DELETE FROM request_logs WHERE id = ?", (last["id"],))
    conn.commit()
    stats = conn.execute("SELECT COUNT(*), AVG(latency_ms) FROM request_logs").fetchone()
    count = stats[0] or 0
    avg = round(stats[1] or 0, 1)
    print(f"Done. Remaining: {count} records, new avg latency: {avg}ms")
else:
    print("No records found in request_logs.")
conn.close()
