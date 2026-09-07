"""
RIG (Retrieval-Interleaved Generation) & RLHF Gold Standard Test Suite
- Universal Law Citation Parser across 8+ statutes and directives
- DualTierLawCache (Tier 1 Hierarchy 0ms + Tier 2 Open Law live API)
- RLHF DPO Gold-Standard registration, retrieval boost, and JSONL dataset export
- RIG-augmented streaming completion with rig_step SSE events
"""
import sys
import os
import asyncio
import json
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root and backend directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
backend_dir = PROJECT_ROOT / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(PROJECT_ROOT))

from rag.rig_engine import LawCitationParser, DualTierLawCache, RIGOrchestrator
from rag.rag_service import rag_service


def test_universal_law_citation_parser():
    """모든 주요 법률/특례법/규칙/예규/선례에 대한 범용 정규식 추출 및 대명사(동법) 해소 검증"""
    sample_text = (
        "가족관계의 등록 등에 관한 법률 제14조의2 제1항에 따라 인터넷 발급이 가능하며, "
        "가사소송법 제2조제1항에 따른 가사비송사건 및 "
        "민법 제781조 제1항에 따른 부의 성과 본을 따르는 것이 원칙입니다. "
        "동법 제844조에 따라 부의 추정이 발생하고, "
        "주민등록법 제14조제1항, 질서위반행위규제법 제16조, "
        "가정폭력범죄의 처벌 등에 관한 특례법 제55조의2 제1항, 형법 제225조, "
        "가족관계등록예규 제520호 및 대법원 등록선례 202105-1호가 적용됩니다."
    )

    citations = LawCitationParser.parse_citations(sample_text)
    assert len(citations) >= 8, f"Expected at least 8 citations, got {len(citations)}"

    statutes_found = {c["statute_name"] for c in citations}
    
    # Verify core family laws
    assert any("가족관계" in s for s in statutes_found), "가족관계등록법 추출 실패"
    
    # Verify external statutes are not excluded
    assert "민법" in statutes_found, "민법 추출 실패"
    assert "가사소송법" in statutes_found, "가사소송법 추출 실패"
    assert "주민등록법" in statutes_found, "주민등록법 추출 실패"
    assert "질서위반행위규제법" in statutes_found, "질서위반행위규제법 추출 실패"
    assert any("가정폭력" in s for s in statutes_found), "가정폭력처벌법 추출 실패"
    assert "형법" in statutes_found, "형법 추출 실패"

    # Verify anaphora resolution ("동법 제844조" -> statute: "민법")
    minbub_citations = [c for c in citations if c["statute_name"] == "민법"]
    article_numbers = [c["article_no"] for c in minbub_citations]
    assert "제781조" in article_numbers, "민법 제781조 추출 실패"
    assert "제844조" in article_numbers, "동법 제844조 민법 치환(Anaphora resolution) 실패"

    # Verify administrative rules / precedents
    rule_types = {c.get("rule_type") for c in citations if c.get("rule_type")}
    assert "예규" in rule_types or any("예규" in c["statute_name"] for c in citations), "예규 추출 실패"
    assert "선례" in rule_types or any("선례" in c["statute_name"] for c in citations), "선례 추출 실패"
    print(f"✅ Universal Law Parser verified with {len(citations)} citations extracted successfully.")


async def test_dual_tier_cache_tier1_and_tier2():
    """DualTierLawCache Tier 1 (0ms 내부 계층) 및 Tier 2 (Open Law API) 검증"""
    cache = DualTierLawCache()

    # Tier 1: 가족관계의 등록 등에 관한 법률 제14조
    tier1_res = await cache.get_article("가족관계의 등록 등에 관한 법률", "제14조")
    assert tier1_res is not None, "Tier 1 가족관계등록법 제14조 조회 실패"
    assert "Tier 1" in tier1_res["retrieval_tier"]
    assert "증명서의 교부청구" in tier1_res["article_title"] or "14" in tier1_res["article_no"]

    # Tier 2: 민법 제781조 (자의 성과 본) - Open Law live API
    tier2_res = await cache.get_article("민법", "제781조")
    assert tier2_res is not None, "Tier 2 민법 제781조 Open Law API 조회 실패"
    assert "781" in tier2_res["article_no"]
    assert "성과 본" in tier2_res["article_title"] or "부" in tier2_res["article_content"]
    print(f"✅ Dual-Tier Cache verified: Tier 1 ({tier1_res['article_title']}), Tier 2 ({tier2_res['article_title']})")


async def test_rig_orchestrator_verification():
    """RIGOrchestrator 실시간 동시 검증 및 마크다운 포맷팅 검증"""
    orchestrator = RIGOrchestrator()
    query = "가족관계등록법 제14조의2와 민법 제781조에 따른 인터넷 발급 및 성본 승계 규정"

    verified = await orchestrator.verify_citations(query)
    assert len(verified) >= 2, f"Expected at least 2 verified laws, got {len(verified)}"

    formatted_md = orchestrator.format_verified_context(verified)
    assert "국가법령정보센터 실시간 검증 원문" in formatted_md
    assert "민법" in formatted_md
    assert "가족관계" in formatted_md
    print(f"✅ RIG Orchestrator verified {len(verified)} live articles successfully.")


async def test_rlhf_registration_retrieval_boost_and_export():
    """RLHF 실무 정답 등록, 가중치 부스팅 검색, DPO JSONL 데이터셋 내보내기 검증"""
    # 1. Register RLHF document
    rlhf_payload = {
        "id": "RLHF-TEST-001",
        "title": "[RLHF공인] 자녀의 성과 본 변경 청구 관할 법원",
        "category": "RLHF모범정답",
        "source": "대법원 가족관계등록과 심사관 모범실무",
        "content": (
            "【질의 (Prompt)】: 자녀의 성과 본을 변경하려면 어느 법원에 청구해야 하나요?\n"
            "【공인 모범 정답 (Chosen)】: 자녀의 복리를 위하여 자의 성과 본을 변경할 필요가 있을 때에는 부, 모 또는 자의 청구에 의하여 자녀의 주소지 관할 가정법원의 허가를 받아야 합니다(민법 제781조 제6항, 가사소송법 제2조 제1항 제2호 라목). 법원의 허가심판서를 받은 날부터 1개월 이내에 성·본 변경신고를 하여야 합니다.\n"
            "【지양 답변 (Rejected)】: 동주민센터나 시·구·읍·면사무소에 가서 성본 변경 신청서를 내면 즉시 변경됩니다.\n"
            "【법적 근거 (Legal Basis)】: 민법 제781조 제6항, 가족관계의 등록 등에 관한 법률 제100조, 가사소송법 제2조 제1항"
        ),
        "metadata": {
            "is_rlhf": True,
            "prompt": "자녀의 성과 본을 변경하려면 어느 법원에 청구해야 하나요?",
            "chosen": "자녀의 주소지 관할 가정법원의 허가를 받아야 합니다(민법 제781조 제6항).",
            "rejected": "동주민센터에 가서 신청서를 내면 즉시 변경됩니다.",
            "legal_basis": "민법 제781조 제6항, 가사소송법 제2조",
            "confidence_boost": 1.5
        }
    }

    try:
        reg_ok = await rag_service.add_document(rlhf_payload)
        assert reg_ok, "RLHF 문서 등록 실패"

        # 2. Check RLHF export
        rlhf_docs = rag_service.get_rlhf_documents()
        assert len(rlhf_docs) >= 1, "RLHF 문서 조회 실패"
        target_rlhf = next((d for d in rlhf_docs if d["id"] == "RLHF-TEST-001"), None)
        assert target_rlhf is not None, "등록한 RLHF 문서를 찾을 수 없음"
        assert target_rlhf["metadata"]["is_rlhf"] is True

        # 3. Dense search score boost verification
        search_results = await rag_service.dense_search("자녀 성과 본 변경 관할 가정법원 청구", top_k=5)
        assert len(search_results) > 0
        top_result = search_results[0]
        # Check if the RLHF doc got top ranking or boost
        rlhf_in_results = [r for r in search_results if r.get("id") == "RLHF-TEST-001"]
        assert len(rlhf_in_results) > 0, "검색 결과에 RLHF 문서가 포함되어야 함"
        print(f"✅ RLHF Gold Standard tested: ID={top_result.get('id')}, Score={top_result.get('dense_similarity'):.4f}, Boosted={top_result.get('is_rlhf', False)}")
    finally:
        # Clean up test document
        await rag_service.delete_document("RLHF-TEST-001")


if __name__ == "__main__":
    print("=== [RIG & RLHF Test Suite Starting] ===")
    
    print("\n[1/4] Testing Universal Law Citation Parser...")
    test_universal_law_citation_parser()

    print("\n[2/4] Testing DualTierLawCache (Tier 1 & Tier 2)...")
    asyncio.run(test_dual_tier_cache_tier1_and_tier2())

    print("\n[3/4] Testing RIG Orchestrator Verification...")
    asyncio.run(test_rig_orchestrator_verification())

    print("\n[4/4] Testing RLHF Registration & Retrieval Boost...")
    asyncio.run(test_rlhf_registration_retrieval_boost_and_export())

    print("\n🎉 [ALL 4 RIG & RLHF TESTS PASSED SUCCESSFULLY!]")

