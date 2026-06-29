import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
from app.generation.streaming import stream_answer

async def main():
    q = "What is the API rate limit?"
    print(f"Querying streaming answer for: {repr(q)}")
    print("=" * 60)

    # 1. First run: should stream token by token (cache miss)
    t0 = time.perf_counter()
    first_token_time = None
    total_tokens = 0
    full_response = []

    async for event_line in stream_answer(q, user_role="admin"):
        if not event_line.strip():
            continue
        # Print event details
        import json
        evt = json.loads(event_line.strip())
        event_type = evt.get("event")
        data = evt.get("data", {})

        if event_type == "generation_token":
            if first_token_time is None:
                first_token_time = time.perf_counter() - t0
                print(f"\n[Cache Miss] Time to first token: {first_token_time*1000:.1f} ms")
            token = data.get("token", "")
            print(token, end="", flush=True)
            total_tokens += 1
            full_response.append(token)
        elif event_type == "final_sources":
            print(f"\n[Cache Miss] Final sources received.")
            print(f"  Confidence: {data.get('confidence')}")
            print(f"  Sources: {data.get('sources')}")

    total_time = time.perf_counter() - t0
    print(f"Total stream time: {total_time*1000:.1f} ms")
    print("=" * 60)

    # 2. Second run: should be a Cache HIT!
    print("Running second query (expecting Cache HIT)...")
    t0 = time.perf_counter()
    first_token_time = None
    full_response = []

    async for event_line in stream_answer(q, user_role="admin"):
        if not event_line.strip():
            continue
        evt = json.loads(event_line.strip())
        event_type = evt.get("event")
        data = evt.get("data", {})

        if event_type == "generation_token":
            if first_token_time is None:
                first_token_time = time.perf_counter() - t0
                print(f"\n[Cache Hit] Time to first token: {first_token_time*1000:.1f} ms")
            token = data.get("token", "")
            print(token, end="", flush=True)
            full_response.append(token)
        elif event_type == "final_sources":
            print(f"\n[Cache Hit] Final sources received.")
            print(f"  Confidence: {data.get('confidence')}")

    total_time = time.perf_counter() - t0
    print(f"Total stream time (Cache Hit): {total_time*1000:.1f} ms")

if __name__ == "__main__":
    asyncio.run(main())
