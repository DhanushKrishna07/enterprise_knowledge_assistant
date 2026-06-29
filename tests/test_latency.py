import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
from app.indexing.embeddings import embed_query
from app.retrieval.hybrid import hybrid_retrieve
from app.generation.ollama_client import chat_complete
from app.core.config import get_settings

async def main():
    settings = get_settings()
    print("Settings:")
    print(f"  llm_model: {settings.llm_model}")
    print(f"  ollama_base_url: {settings.ollama_base_url}")
    print(f"  embedding_model: {settings.embedding_model}")
    print(f"  reranker_model: {settings.reranker_model}")
    print("-" * 50)

    # 1. Test embedding query
    print("Testing embed_query...")
    t0 = time.perf_counter()
    vec = embed_query("How many days of Earned Leave do employees get annually?")
    print(f"embed_query took: {(time.perf_counter() - t0)*1000:.1f} ms (vec len={len(vec)})")

    # 2. Test hybrid retrieval
    print("\nTesting hybrid_retrieve...")
    t0 = time.perf_counter()
    ret = hybrid_retrieve("How many days of Earned Leave do employees get annually?", user_role="admin")
    print(f"hybrid_retrieve took: {(time.perf_counter() - t0)*1000:.1f} ms")
    print(f"  semantic count: {len(ret['semantic_results'])}")
    print(f"  keyword count: {len(ret['keyword_results'])}")
    print(f"  fused count: {len(ret['fused_candidates'])}")

    # 3. Test Ollama chat complete
    print("\nTesting Ollama chat_complete (small)...")
    t0 = time.perf_counter()
    try:
        ans = await chat_complete([{"role": "user", "content": "Hello! Say hi in exactly 1 word."}], model=settings.llm_model, max_tokens=10)
        print(f"chat_complete took: {(time.perf_counter() - t0)*1000:.1f} ms")
        print(f"  Response: {repr(ans)}")
    except Exception as e:
        print(f"chat_complete failed: {e}")

    # 4. Test Ollama chat complete (RAG prompt size)
    print("\nTesting Ollama chat_complete (RAG prompt size)...")
    context_text = "\n\n".join([c.get("text", "") for c in ret['fused_candidates'][:3]])
    prompt_msgs = [
        {"role": "system", "content": f"You are a helpful assistant. Answer the user's question based only on the following context:\n\n{context_text}"},
        {"role": "user", "content": "How many days of Earned Leave do employees get annually?"}
    ]
    t0 = time.perf_counter()
    try:
        ans = await chat_complete(prompt_msgs, model=settings.llm_model, max_tokens=256)
        print(f"chat_complete (RAG) took: {(time.perf_counter() - t0)*1000:.1f} ms")
        print(f"  Response: {repr(ans)}")
    except Exception as e:
        print(f"chat_complete (RAG) failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
