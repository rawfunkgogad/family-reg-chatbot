import asyncio
import sys
import json
import time
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from llm_client import stream_chat_completion
from optimization.cache_manager import cache_manager

async def test_cache_and_regen_flow():
    print("=" * 65)
    print("1. 초기 질의 (Live LLM 호출 및 캐시 적재)")
    print("=" * 65)
    
    query = "가족관계증명서 발급 시 일반과 상세의 차이점 요약"
    messages = [{"role": "user", "content": query}]

    # Clean cache key if exists
    cache_manager.clear()
    
    t0 = time.time()
    resp1_chunks = []
    resp1_cached = None
    async for chunk in stream_chat_completion(messages, mode="unified", model="llama-3.3-70b", bypass_cache=False):
        if chunk["type"] == "cache_status":
            resp1_cached = chunk["data"]["is_cached"]
        elif chunk["type"] == "delta":
            resp1_chunks.append(chunk["data"])
    
    duration1 = time.time() - t0
    print(f"-> 1회차 질의 시간: {duration1:.2f}초, 캐시적중 여부: {resp1_cached}")
    assert resp1_cached is False, "첫 질의는 실시간 생성이어야 합니다."
    assert len("".join(resp1_chunks)) > 50

    print("\n" + "=" * 65)
    print("2. 동일 질의 재요청 (고속 캐시 즉시 적중 검증)")
    print("=" * 65)

    t0 = time.time()
    resp2_chunks = []
    resp2_cached = None
    async for chunk in stream_chat_completion(messages, mode="unified", model="llama-3.3-70b", bypass_cache=False):
        if chunk["type"] == "cache_status":
            resp2_cached = chunk["data"]["is_cached"]
        elif chunk["type"] == "delta":
            resp2_chunks.append(chunk["data"])
    
    duration2 = time.time() - t0
    print(f"-> 2회차 캐시 질의 시간: {duration2:.3f}초, 캐시적중 여부: {resp2_cached}")
    assert resp2_cached is True, "두 번째 동일 질의는 캐시에서 즉시 반환되어야 합니다."
    assert duration2 < 0.1, "캐시 응답은 0.1초 미만이어야 합니다."

    print("\n" + "=" * 65)
    print("3. '실시간 재추론 (새 답변)' 요청 (bypass_cache=True 검증)")
    print("=" * 65)

    t0 = time.time()
    resp3_chunks = []
    resp3_cached = None
    async for chunk in stream_chat_completion(messages, mode="unified", model="llama-3.3-70b", bypass_cache=True):
        if chunk["type"] == "cache_status":
            resp3_cached = chunk["data"]["is_cached"]
        elif chunk["type"] == "delta":
            resp3_chunks.append(chunk["data"])
    
    duration3 = time.time() - t0
    print(f"-> 3회차 캐시 우회 실시간 재추론 시간: {duration3:.2f}초, 캐시적중 여부: {resp3_cached}")
    assert resp3_cached is False, "bypass_cache=True 시 캐시를 우회하고 실시간 생성되어야 합니다."
    assert len("".join(resp3_chunks)) > 50

    print("\n🎉 [고속 캐시 표시 & 실시간 AI 재추론 파이프라인 전체 검증 완료!]")

if __name__ == "__main__":
    asyncio.run(test_cache_and_regen_flow())
