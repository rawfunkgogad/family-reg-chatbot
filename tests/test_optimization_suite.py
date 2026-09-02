import asyncio
import sys
import time
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from optimization.cache_manager import cache_manager
from optimization.metrics_collector import metrics_collector
from llm_client import stream_chat_completion

async def test_optimization_suite():
    print("=" * 65)
    print("1. llama-3.3-70b RAG 스트리밍 & 최초 캐시 미스(Cache Miss) 검증")
    print("=" * 65)
    cache_manager.clear()
    
    query = "가족관계증명서 인터넷으로 무료로 발급받는 방법과 수수료 안내"
    messages = [{"role": "user", "content": query}]

    start_t = time.time()
    first_response = ""
    first_metrics = None

    async for chunk in stream_chat_completion(
        messages=messages,
        temperature=0.5,
        mode="civilian",
        model="llama-3.3-70b"
    ):
        if chunk["type"] == "delta":
            first_response += chunk["data"]
        elif chunk["type"] == "metrics":
            first_metrics = chunk["data"]

    elapsed_1 = (time.time() - start_t) * 1000
    print(f"-> 1회차 요청 완료 (소요시간: {elapsed_1:.1f}ms, 캐시 적중 여부: {first_metrics.get('cached')})")
    print(f"-> 토큰 추정치: {first_metrics.get('total_tokens')} tokens (모델: {first_metrics.get('model')})")
    print(f"-> 응답 앞부분: {first_response[:100]}...")
    assert first_metrics.get("cached") is False
    assert len(first_response) > 50

    print("\n" + "=" * 65)
    print("2. 동일 질의 2회차 요청: 질의응답 캐시 적중(Cache Hit) 초고속 반환 검증")
    print("=" * 65)
    start_t2 = time.time()
    second_response = ""
    second_metrics = None

    async for chunk in stream_chat_completion(
        messages=messages,
        temperature=0.5,
        mode="civilian",
        model="llama-3.3-70b"
    ):
        if chunk["type"] == "delta":
            second_response += chunk["data"]
        elif chunk["type"] == "metrics":
            second_metrics = chunk["data"]

    elapsed_2 = (time.time() - start_t2) * 1000
    print(f"-> 2회차 요청 완료 (소요시간: {elapsed_2:.1f}ms, 캐시 적중 여부: {second_metrics.get('cached')})")
    print(f"-> 캐시 적중으로 지연시간 획기적 단축 확인! (1회차 {elapsed_1:.0f}ms -> 2회차 {elapsed_2:.0f}ms)")
    assert second_metrics.get("cached") is True
    assert elapsed_2 < 50.0 # under 50ms!
    assert second_response == first_response

    print("\n" + "=" * 65)
    print("3. gpt-oss-120b 심층 추론 모델 전환 검증")
    print("=" * 65)
    gpt_msg = [{"role": "user", "content": "전산오기 직권정정 요건과 대법원 규칙 제60조"}]
    gpt_response = ""
    gpt_metrics = None

    async for chunk in stream_chat_completion(
        messages=gpt_msg,
        temperature=0.4,
        mode="official",
        model="gpt-oss-120b"
    ):
        if chunk["type"] == "delta":
            gpt_response += chunk["data"]
        elif chunk["type"] == "metrics":
            gpt_metrics = chunk["data"]

    print(f"-> gpt-oss-120b 심층 추론 완료 (모델: {gpt_metrics.get('model')}, 지연시간: {gpt_metrics.get('latency_ms')}ms)")
    print(f"-> 응답 앞부분: {gpt_response[:100]}...")
    assert gpt_metrics.get("model") == "gpt-oss-120b"

    print("\n" + "=" * 65)
    print("4. 통계 집계 검증 (Cache Stats & Metrics Summary)")
    print("=" * 65)
    c_stats = cache_manager.get_stats()
    m_summary = metrics_collector.get_summary()
    print(f"-> 캐시 적중률: {c_stats['hit_rate_pct']}% ({c_stats['cache_hits']}/{c_stats['total_queries']})")
    print(f"-> 누적 절감 토큰: {c_stats['total_saved_tokens']} tokens")
    print(f"-> 평균 지연시간: {m_summary['avg_latency_ms']} ms")
    assert c_stats["cache_hits"] >= 1
    assert c_stats["total_saved_tokens"] > 0

    print("\n🎉 [llama-3.3-70b 및 비용/지연시간 최적화 전체 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_optimization_suite())
