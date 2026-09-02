import asyncio
import sys
import json
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from rag.rag_service import rag_service
from rag.document_parser import parse_json

async def test_admin_flow():
    print("=" * 60)
    print("1. RAG 관리자 지식 등록 및 bge-m3 실시간 증분 임베딩 테스트")
    print("=" * 60)
    
    # Initialize
    await rag_service.initialize()
    initial_count = len(rag_service.get_all_documents())
    print(f"-> 초기 등록 문서 수: {initial_count}건")

    # Sample JSON document to upload
    sample_json_data = [
        {
            "category": "출생신고",
            "source": "가족관계의 등록 등에 관한 법률 제46조 / 2026 개정 실무지침",
            "title": "의료기관 출생통보제 및 직권 출생기록 절차",
            "content": "의료기관의 장은 자녀가 출생한 날부터 14일 이내에 건강보험심사평가원에 출생정보를 제출하여야 하며, 시·구·읍·면의 장은 심평원으로부터 출생통보를 받았음에도 부모가 1개월 이내에 출생신고를 하지 아니한 때에는 최고 후 감독법원의 허가를 받아 직권으로 출생기록을 마쳐야 한다."
        }
    ]
    json_bytes = json.dumps(sample_json_data, ensure_ascii=False).encode('utf-8')
    parsed_docs = parse_json(json_bytes, "birth_notification_2026.json")
    print(f"-> JSON 파싱 완료: {len(parsed_docs)}개 지식 청크")

    # Add and embed
    added = await rag_service.add_documents(parsed_docs)
    print(f"-> bge-m3 임베딩 생성 및 인덱스 병합 완료: +{added}건")
    assert len(rag_service.get_all_documents()) == initial_count + 1

    print("\n" + "=" * 60)
    print("2. 신규 등록된 지식에 대한 2단계 RAG 검색 즉시 반영 검증")
    print("=" * 60)
    test_query = "의료기관 출생통보제에서 부모가 출생신고 안 하면 직권으로 기록하나요?"
    print(f"질의: '{test_query}'")
    
    retrieved = await rag_service.retrieve(test_query, top_k=3)
    print("-> 검색 및 리랭크 결과:")
    for i, doc in enumerate(retrieved, 1):
        print(f"  [{i}] {doc['title']} (리랭크 점수: {doc.get('rerank_score', 0):.4f})")
    
    assert len(retrieved) > 0
    assert "출생통보" in retrieved[0]["title"]
    print("-> 방금 등록한 지식이 Top 1위로 정확하게 검색됨!")

    print("\n" + "=" * 60)
    print("3. 등록 지식 삭제 및 인덱스 갱신 테스트")
    print("=" * 60)
    target_id = parsed_docs[0]["id"]
    deleted = await rag_service.delete_document(target_id)
    print(f"-> 문서 ID({target_id}) 삭제 결과: {deleted}")
    assert deleted is True
    assert len(rag_service.get_all_documents()) == initial_count
    print(f"-> 삭제 후 문서 수: {len(rag_service.get_all_documents())}건 (원상 복구 완료)")

    print("\n🎉 [관리자 문서 등록 & 실시간 임베딩 전체 플로우 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_admin_flow())
