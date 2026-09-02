import asyncio
import sys
import json
import urllib.request
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from llm_client import stream_chat_completion

async def test_unified_assistant():
    print("=" * 65)
    print("1. 단일 통합 어시스턴트: 대민 민원 & 무료 발급 질의 검증")
    print("=" * 65)
    
    civil_msg = [{"role": "user", "content": "가족관계증명서 인터넷 무료 발급 방법과 일반/상세 차이점"}]
    civil_response = ""
    async for chunk in stream_chat_completion(civil_msg, mode="unified", model="llama-3.3-70b"):
        if chunk["type"] == "delta":
            civil_response += chunk["data"]

    print(f"-> 민원 질의 응답 앞부분 (200자):\n{civil_response[:200]}...\n")
    assert "가족관계증명서" in civil_response
    assert "무료" in civil_response or "0원" in civil_response or "efamily" in civil_response

    print("=" * 65)
    print("2. 단일 통합 어시스턴트: 실무 심사 & 상하위 법령 위계 질의 검증")
    print("=" * 65)

    legal_msg = [{"role": "user", "content": "전산오기 직권정정의 상하위 법률, 규칙, 예규, 선례의 위임관계와 심사 기준"}]
    legal_response = ""
    async for chunk in stream_chat_completion(legal_msg, mode="unified", model="llama-3.3-70b"):
        if chunk["type"] == "delta":
            legal_response += chunk["data"]

    print(f"-> 실무 법령 질의 응답 앞부분 (200자):\n{legal_response[:200]}...\n")
    assert "가족관계" in legal_response or "직권정정" in legal_response

    print("=" * 65)
    print("3. 통합 추천 케이스 API (/api/quick-cases) 검증")
    print("=" * 65)
    with urllib.request.urlopen("http://127.0.0.1:8000/api/quick-cases") as res:
        cases = json.loads(res.read().decode('utf-8'))
        print(f"-> 통합 추천 케이스 수: {len(cases)}건")
        assert len(cases) >= 6
        for c in cases[:4]:
            print(f"   [{c['category']}] {c['title']}")

    print("\n🎉 [단일 통합 AI 어시스턴트 전환 및 기능 검증 전체 성공!]")

if __name__ == "__main__":
    asyncio.run(test_unified_assistant())
