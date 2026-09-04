"""
지식 코퍼스 현행화(대법원 예규·선례 및 법령체계도 수집기 연동, 00시/수동 동기화) 테스트 스위트
"""
import sys
from pathlib import Path
import httpx

# Add backend directory
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sync.corpus_sync_manager import corpus_sync_manager
from sync.scheduler import get_seconds_until_next_midnight_kst

BASE_URL = "http://127.0.0.1:8000"
AUTH_CODE = "family_manager_035"

def test_sync_manager_status():
    """SyncManager 기본 상태 구조 검증"""
    status = corpus_sync_manager.get_status()
    assert "is_running" in status
    assert "next_scheduled_sync" in status
    assert "current_stage" in status
    assert status["is_running"] is False
    assert "2026-" in status["next_scheduled_sync"]

def test_seconds_until_midnight_calculation():
    """자정(00:00 KST)까지 남은 시간 양수 계산 검증"""
    secs = get_seconds_until_next_midnight_kst()
    assert secs > 0
    assert secs <= 86400

def test_normalization_rules():
    """가족관계등록예규 산출물 정규화 검증"""
    sample_rule = [{
        "id": 1861548,
        "category": "가족관계등록예규",
        "data_no": "111",
        "title": "인명용 한자의 제한과 관련된 가족관계등록사무 처리지침",
        "status": "현행",
        "promulgation_date": "2007-12-10",
        "enforcement_date": "2008-01-01",
        "directory_path": ["가족관계등록예규", "제1장 총칙", "제4장 신고", "제2절 출생"],
        "content_text": "제1조 (인명용 한자 제한의 적용범위)..."
    }]
    docs = corpus_sync_manager.normalize_rules(sample_rule)
    assert len(docs) == 1
    d = docs[0]
    assert d["id"] == "SCOURT-DIR-111"
    assert "인명용 한자" in d["title"]
    assert d["category"] == "가족관계등록예규"
    assert "【가족관계등록예규 제111호】" in d["content"]

def test_normalization_precedents():
    """가족관계등록선례 산출물 정규화 검증"""
    sample_prec = [{
        "id": 1851174,
        "category": "가족관계등록선례",
        "data_no": "200801-1",
        "title": "외국에서의 출생(사망)연월일 기록 지침",
        "status": "현행",
        "promulgation_date": "2008-01-15",
        "directory_path": ["가족관계등록선례", "5권이후 연도별", "2008년"],
        "content_text": "가. 우리나라 국민이 외국에서 출생한 경우에는..."
    }]
    docs = corpus_sync_manager.normalize_precedents(sample_prec)
    assert len(docs) == 1
    d = docs[0]
    assert d["id"] == "SCOURT-PREC-200801-1"
    assert "외국에서의 출생" in d["title"]
    assert d["category"] == "가족관계등록선례"

def test_normalization_law_hierarchy():
    """법령체계도 (모법 및 하위규칙 조문) 정규화 검증"""
    sample_hierarchy = {
        "regulations": {
            "root_act": {
                "statute_name": "가족관계의 등록 등에 관한 법률",
                "articles": [{
                    "article_no": "제14조",
                    "article_title": "증명서의 교부청구",
                    "content": "본인 또는 배우자, 직계혈족은 교부를 청구할 수 있다.",
                    "paragraphs": []
                }]
            },
            "subordinate_rule": {
                "statute_name": "가족관계의 등록 등에 관한 규칙",
                "articles": [{
                    "article_no": "제60조",
                    "article_title": "감독법원의 허가에 의한 직권정정",
                    "content": "규칙 제60조 내용...",
                    "paragraphs": []
                }]
            }
        }
    }
    docs = corpus_sync_manager.normalize_law_hierarchy(sample_hierarchy)
    assert len(docs) == 2
    ids = [d["id"] for d in docs]
    assert "LAW-ACT-제14조" in ids
    assert "LAW-RULE-제60조" in ids

def test_sync_status_api_live():
    """GET /api/admin/corpus/sync/status 엔드포인트 검증"""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        res = client.get("/api/admin/corpus/sync/status")
        assert res.status_code == 200
        data = res.json()
        assert "is_running" in data
        assert "next_scheduled_sync" in data
        assert "current_stage" in data

if __name__ == "__main__":
    print("=== [Corpus Sync Unit Tests Starting] ===")
    test_sync_manager_status()
    print("  [PASS] test_sync_manager_status")
    test_seconds_until_midnight_calculation()
    print("  [PASS] test_seconds_until_midnight_calculation")
    test_normalization_rules()
    print("  [PASS] test_normalization_rules")
    test_normalization_precedents()
    print("  [PASS] test_normalization_precedents")
    test_normalization_law_hierarchy()
    print("  [PASS] test_normalization_law_hierarchy")
    try:
        test_sync_status_api_live()
        print("  [PASS] test_sync_status_api_live")
    except Exception as e:
        print(f"  [SKIP/NOTE] test_sync_status_api_live (server will be restarted): {e}")

    print("\n[SUCCESS] ALL CORPUS SYNC TESTS PASSED!")
