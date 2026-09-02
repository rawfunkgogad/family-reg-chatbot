import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from llm_client import stream_chat_completion

async def test_stream():
    print("Testing stream_chat_completion...")
    messages = [
        {"role": "user", "content": "출생신고서 원본에는 모의 주민등록번호가 맞게 적혀 있는데, 전산입력 착오로 잘못 등록된 경우 간이직권정정(감독법원 허가 불요)이 가능한가요?"}
    ]
    response_text = ""
    async for chunk in stream_chat_completion(messages, temperature=0.3, max_tokens=500):
        response_text += chunk
        print(chunk, end="", flush=True)
    
    print("\n\n--- Stream Test Complete ---")
    assert "직권" in response_text or "18조" in response_text or "규칙" in response_text
    print("Verification Passed!")

if __name__ == "__main__":
    asyncio.run(test_stream())
