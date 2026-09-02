import asyncio
import sys
import json
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from rag.rag_service import rag_service
from llm_client import stream_chat_completion

async def test_efamily_integration():
    print("=" * 65)
    print("1. e-family 전자가족관계등록시스템 코퍼스 초기화 및 RAG 검색 검증")
    print("=" * 65)
    await rag_service.initialize()
    print(f"-> 코퍼스 크기: {len(rag_service.get_all_documents())}건")

    # Test efamily queries
    queries = [
        "가족관계증명서 일반과 상세 차이가 무엇이고 인터넷에서 무료로 발급받는 방법",
        "법원에서 개명허가 결정 받았는데 전자가족관계등록시스템에서 인터넷 개명신고 하는 방법",
        "인쇄할 때 프린터 오류 나면 PDF로 어떻게 저장하나요?"
    ]

    for q in queries:
        print(f"\n[질의]: '{q}'")
        retrieved = await rag_service.retrieve(q, top_k=2)
        for i, doc in enumerate(retrieved, 1):
            print(f"  -> Top {i}: {doc['title']} (리랭크 점수: {doc.get('rerank_score', 0):.4f})")
            print(f"     출처: {doc['source']}")
        assert len(retrieved) > 0

    print("\n" + "=" * 65)
    print("2. 대민 민원 상담 모드 (mode='civilian') 스트리밍 검증")
    print("=" * 65)
    civil_msg = [{"role": "user", "content": "가족관계증명서 인터넷으로 무료로 뽑으려면 어떻게 하나요?"}]
    civil_chunks = 0
    civil_text = ""
    async for event in stream_chat_completion(civil_msg, temperature=0.3, max_tokens=400, mode="civilian"):
        if event["type"] == "delta":
            civil_chunks += 1
            civil_text += event["data"]

    print(f"-> 민원 상담 모드 응답 생성 완료 ({civil_chunks} 토큰 청크)")
    print(f"-> 응답 앞부분:\n{civil_text[:200]}...")
    assert "efamily" in civil_text or "전자가족관계등록시스템" in civil_text or "무료" in civil_text or "발급" in civil_text

    print("\n" + "=" * 65)
    print("3. 공무원 실무 심사 모드 (mode='official') 스트리밍 검증")
    print("=" * 65)
    off_msg = [{"role": "user", "content": "전산오기 직권정정 요건"}]
    off_chunks = 0
    off_text = ""
    async for event in stream_chat_completion(off_msg, temperature=0.3, max_tokens=400, mode="official"):
        if event["type"] == "delta":
            off_chunks += 1
            off_text += event["data"]

    print(f"-> 공무원 실무 모드 응답 생성 완료 ({off_chunks} 토큰 청크)")
    print(f"-> 응답 앞부분:\n{off_text[:200]}...")
    assert "직권" in off_text or "18조" in off_text or "법" in off_text

    print("\n🎉 [전자가족관계등록시스템 민원 연계 & 듀얼 모드 전체 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_efamily_integration())
