import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from rag.rag_service import rag_service
from llm_client import stream_chat_completion

async def test_full_rag():
    print("=" * 60)
    print("1. RAG 지식 코퍼스 초기화 및 bge-m3 임베딩 생성/로드 테스트")
    print("=" * 60)
    await rag_service.initialize()
    assert rag_service.embeddings is not None
    print(f"-> 임베딩 벡터 로드 완료: Shape = {rag_service.embeddings.shape}")

    print("\n" + "=" * 60)
    print("2. 2단계 RAG 검색 (bge-m3 유사도 검색 -> bge-reranker-v2-m3 정밀 리랭킹)")
    print("=" * 60)
    test_query = "생모의 인적사항을 모르는 미혼부의 자녀 출생신고 요건"
    print(f"질의: '{test_query}'")
    
    retrieved = await rag_service.retrieve(test_query, top_k=3)
    print(f"-> 검색 및 리랭크 완료 (총 {len(retrieved)}건 선별):")
    for i, doc in enumerate(retrieved, 1):
        print(f"  [{i}] {doc['title']} (리랭크 점수: {doc.get('rerank_score', 0):.4f})")
        print(f"      출처: {doc['source']}")
    
    assert len(retrieved) > 0
    assert "미혼부" in retrieved[0]["title"] or "57조" in retrieved[0]["source"] or "출생" in retrieved[0]["title"]

    print("\n" + "=" * 60)
    print("3. RAG 주입 gpt-oss-120b 스트리밍 응답 테스트")
    print("=" * 60)
    messages = [{"role": "user", "content": test_query}]
    sources_received = False
    chunks_count = 0
    sample_text = ""
    
    async for event in stream_chat_completion(messages, temperature=0.3, max_tokens=500, use_rag=True):
        if event["type"] == "sources":
            sources_received = True
            print(f"-> [Event: sources] {len(event['data'])}개 근거 수신:")
            for s in event['data']:
                print(f"   - {s['title']} ({s['source']})")
        elif event["type"] == "delta":
            chunks_count += 1
            sample_text += event["data"]
            if chunks_count <= 15:
                print(event["data"], end="", flush=True)

    print("\n... [스트리밍 완료]")
    assert sources_received, "Sources metadata was not received!"
    assert chunks_count > 0, "No content chunks generated!"

    print("\n" + "=" * 60)
    print("4. /v1/agent/chat 웹 검색 에이전트 연동 테스트")
    print("=" * 60)
    agent_res = await rag_service.execute_web_agent("대법원 가족관계등록예규 검색")
    print(f"-> 웹 에이전트 응답 성공 여부: {'answer' in agent_res}")
    print(f"-> 답변 앞부분: {agent_res.get('answer', '')[:100]}...")

    print("\n🎉 [전체 RAG 파이프라인 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_full_rag())
