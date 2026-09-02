import asyncio
import sys
import json
import urllib.request
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from rag.excel_hierarchy_parser import create_sample_hierarchy_excel, parse_excel_hierarchy
from rag.rag_service import rag_service
from llm_client import stream_chat_completion

async def test_excel_hierarchy_flow():
    print("=" * 65)
    print("1. 엑셀 파일 생성 및 상하위 법률 파서 검증")
    print("=" * 65)
    
    excel_bytes = create_sample_hierarchy_excel()
    assert len(excel_bytes) > 1000, "엑셀 바이트가 유효해야 합니다."
    print(f"-> 표준 엑셀 템플릿 생성 완료 ({len(excel_bytes)} bytes)")

    filename = "상하위법률관계_표준체계_실무편람.xlsx"
    parsed_docs = parse_excel_hierarchy(excel_bytes, filename)
    print(f"-> 엑셀 파싱 완료: {len(parsed_docs)}개 상하위 법령 체인 추출")
    assert len(parsed_docs) >= 5, "최소 5개 이상의 법령 체인이 파싱되어야 합니다."

    for idx, doc in enumerate(parsed_docs, 1):
        hd = doc.get("hierarchy_data", {})
        print(f"   [{idx}] 주제: {hd.get('domain')}")
        print(f"       1단계 법률: {hd.get('primary_law')}")
        print(f"       2단계 규칙: {hd.get('sub_rule')}")
        print(f"       3단계 예규: {hd.get('directive')}")
        print(f"       4단계 선례: {hd.get('precedent')}")
        print(f"       우선순위: {hd.get('priority_rules')[:60]}...")
        assert hd.get("domain") and hd.get("primary_law")

    print("\n" + "=" * 65)
    print("2. 엑셀 상하위 법령 체인 RAG 색인 등록 및 임베딩 생성")
    print("=" * 65)
    added_count = await rag_service.add_documents(parsed_docs)
    print(f"-> {added_count}건의 상하위 법령 체인이 bge-m3로 임베딩 등록되었습니다.")
    print(f"-> 총 코퍼스 문서 수: {len(rag_service.get_all_documents())}건")

    print("\n" + "=" * 65)
    print("3. 상하위 법률 위계 고려 질의응답 (llama-3.3-70b 계층형 법리 추론)")
    print("=" * 65)
    query = "전산오기 직권정정의 상위법률과 대법원규칙, 예규의 위임관계와 우선순위를 설명해주세요."
    messages = [{"role": "user", "content": query}]

    print(f"[질의]: {query}")
    accumulated = ""
    async for chunk in stream_chat_completion(messages, mode="official", model="llama-3.3-70b"):
        if chunk["type"] == "delta":
            accumulated += chunk["data"]

    print(f"\n-> llama-3.3-70b 계층 법리 답변 앞부분 (200자):\n{accumulated[:250]}...\n")
    assert "법률" in accumulated or "규칙" in accumulated or "예규" in accumulated or "직권정정" in accumulated

    print("=" * 65)
    print("4. 파일 단위 그룹화 뷰에서 엑셀 파일 메타데이터 확인")
    print("=" * 65)
    files = rag_service.get_grouped_files()
    excel_files = [f for f in files if f["file_type"] == "EXCEL"]
    print(f"-> 등록된 엑셀 그룹 파일 수: {len(excel_files)}개")
    assert len(excel_files) > 0, "EXCEL 파일 그룹이 존재해야 합니다."
    print(f"   파일명: {excel_files[0]['file_name']}, 항목 수: {excel_files[0]['chunks_count']}개")

    print("\n🎉 [엑셀 기반 상하위 법률 관계 탑재 및 계층형 추론 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_excel_hierarchy_flow())
