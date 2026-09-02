import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from llm_client import stream_chat_completion

async def debug_stream():
    messages = [{"role": "user", "content": "생모의 인적사항을 모르는 미혼부의 자녀 출생신고 요건"}]
    async for event in stream_chat_completion(messages, temperature=0.3, max_tokens=500, use_rag=True):
        print("EVENT:", event["type"], str(event["data"])[:80])

if __name__ == "__main__":
    asyncio.run(debug_stream())
