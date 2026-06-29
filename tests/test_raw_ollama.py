import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import httpx

async def main():
    payload = {
        "model": "qwen3:4b",
        "messages": [{"role": "user", "content": "Say hello in 1 word."}],
        "stream": True,
        "think": True,
        "options": {
            "temperature": 0.0,
            "num_predict": 50,
        }
    }
    url = "http://localhost:11434/api/chat"
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                print(json.dumps(chunk))

if __name__ == "__main__":
    asyncio.run(main())
