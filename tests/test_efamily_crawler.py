"""
대법원 전자가족관계등록시스템 고객센터(FAQ·가이드·신청서식) 크롤러 및 데이터 무결성 검증 테스트
- FAQ 112건, 시스템 이용안내 가이드 3건, 신청서 서식 46건 전수 검증
- HTML 엔티티 언이스케이프, 첨부파일 메타데이터 및 RAG 정규화 무결성 검증
"""
import sys
import json
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sync.corpus_sync_manager import corpus_sync_manager

DATA_FILE = backend_dir / "data" / "efamily_customer_center.json"

def test_crawler_file_existence_and_counts():
    """크롤링 산출물 파일 존재 및 데이터 개수(161건) 검증"""
    assert DATA_FILE.exists(), f"Output file does not exist: {DATA_FILE}"
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    meta = data.get("metadata", {})
    docs = data.get("documents", [])
    
    assert meta.get("faq_count") == 112, f"Expected 112 FAQ items, got {meta.get('faq_count')}"
    assert meta.get("guide_count") == 3, f"Expected 3 Guide items, got {meta.get('guide_count')}"
    assert meta.get("form_count") == 46, f"Expected 46 Form items, got {meta.get('form_count')}"
    assert len(docs) == 161, f"Expected total 161 documents, got {len(docs)}"
    print(f"PASS: test_crawler_file_existence_and_counts (Total 161 items verified)")

def test_document_schema_and_html_cleaning():
    """모든 수집 문서의 필수 스키마 및 HTML 엔티티 정제 검증"""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for doc in data.get("documents", []):
        assert doc.get("id"), "Missing id"
        assert doc.get("category"), f"Missing category in {doc.get('id')}"
        assert doc.get("title"), f"Missing title in {doc.get('id')}"
        assert doc.get("content"), f"Missing content in {doc.get('id')}"
        assert len(doc["content"]) > 20, f"Content too short in {doc.get('id')}"
        
        # HTML entity unescaped check
        assert "&#40;" not in doc["title"], f"Unescaped &#40; found in title: {doc['title']}"
        assert "&#41;" not in doc["title"], f"Unescaped &#41; found in title: {doc['title']}"
        assert "<p>" not in doc["content"] and "<div>" not in doc["content"], f"Raw HTML tags found in {doc.get('id')}"

    print("PASS: test_document_schema_and_html_cleaning (Schema and clean text verified)")

def test_normalization_and_categories():
    """CorpusSyncManager 정규화 파이프라인 연동 검증"""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    norm_docs = corpus_sync_manager.normalize_efamily_customer_center(raw_data)
    assert len(norm_docs) == 161
    
    categories = {d["category"] for d in norm_docs}
    assert "전자가족관계등록 FAQ" in categories
    assert "전자가족관계등록 시스템안내" in categories
    assert "가족관계등록 신청서식" in categories
    
    # ID 접두어 검증
    ids = [d["id"] for d in norm_docs]
    assert any(i.startswith("EFAMILY-FAQ-") for i in ids)
    assert any(i.startswith("EFAMILY-GUIDE-") for i in ids)
    assert any(i.startswith("EFAMILY-FORM-") for i in ids)
    print("PASS: test_normalization_and_categories (RAG normalization and 3 category mappings verified)")

def test_core_forms_and_attachment_metadata():
    """주요 신청 서식(출생신고서, 혼인신고서, 개명신고서, 별지 제11호) 첨부서식 메타데이터 검증"""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    forms = [d for d in data.get("documents", []) if d.get("category") == "가족관계등록 신청서식"]
    titles = [f["title"] for f in forms]
    
    # 주요 법정서식 포함 확인
    assert any("출생신고서" in t for t in titles), "출생신고서 not found in forms"
    assert any("혼인신고서" in t for t in titles), "혼인신고서 not found in forms"
    assert any("개명신고서" in t for t in titles), "개명신고서 not found in forms"
    assert any("제11호" in t for t in titles), "별지 제11호 서식 not found in forms"
    
    # 첨부파일명 검증
    birth_form = next(f for f in forms if "출생신고서" in f["title"])
    assert len(birth_form.get("file_names", [])) > 0, "Birth form has no attachments"
    assert any(".hwp" in fn or ".pdf" in fn for fn in birth_form["file_names"])
    print(f"PASS: test_core_forms_and_attachment_metadata (Key statutory forms verified: {birth_form['file_names']})")

if __name__ == "__main__":
    print("=== [eFamily Customer Center Knowledge Tests Starting] ===")
    test_crawler_file_existence_and_counts()
    test_document_schema_and_html_cleaning()
    test_normalization_and_categories()
    test_core_forms_and_attachment_metadata()
    print("\nALL 4 EFAMILY CRAWLER & KNOWLEDGE TESTS PASSED! (100%)")
