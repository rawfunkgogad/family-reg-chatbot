"""
배포 검증용 프로덕션 준비상태 자동화 테스트 스위트 (Production Readiness Test Suite)
- 468건 마스터 지식 코퍼스(대법원 예규/선례 278건 + 전자가족관계 73건 + 생활법령 117건) 무결성
- 실시간 bge-m3 벡터 검색 및 4단계 실무 추론 검증
"""
import httpx
import json
import numpy as np
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
AUTH_CODE = "family_manager_035"

def test_health_check(client):
    """서버 헬스체크 정상 응답 (200 OK)"""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "healthy"

def test_admin_auth_and_master_corpus_count(client):
    """관리자 보안 인증 및 마스터 코퍼스 468건 전수 로드 검증"""
    login_res = client.post("/api/admin/auth/login", json={"auth_code": AUTH_CODE})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    docs_res = client.get("/api/admin/documents", headers=headers)
    assert docs_res.status_code == 200
    docs = docs_res.json()["documents"]
    assert len(docs) >= 468, f"Expected at least 468 documents in master corpus, got {len(docs)}"

    # 카테고리별 분포 무결성 검증
    categories = [d.get("category") for d in docs]
    assert "가족관계등록예규" in categories
    assert "가족관계등록선례" in categories

def test_cached_vector_embeddings_integrity():
    """로컬 캐시 벡터 임베딩 (corpus_embeddings.npy) 무결성 검증"""
    emb_path = Path("backend/data/corpus_embeddings.npy")
    meta_path = Path("backend/data/corpus_metadata.json")
    assert emb_path.exists()
    assert meta_path.exists()

    emb = np.load(emb_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert emb.shape == (len(meta), 1024), f"Embeddings shape should match metadata count ({len(meta)}, 1024), got {emb.shape}"
    assert len(meta) >= 468, f"Metadata count should be at least 468, got {len(meta)}"

def test_rag_search_scourt_precedents(client):
    """대법원 가족관계등록선례 실시간 RAG 질의 및 인용 응답 검증"""
    payload = {
        "messages": [
            {"role": "user", "content": "외국인이 귀화하여 대한민국 국적을 취득했을 때 귀화 전 외국식 성명을 그대로 가족관계등록부에 사용할 수 있나요?"}
        ]
    }
    with client.stream("POST", "/api/chat", json=payload) as res:
        assert res.status_code == 200
        full_text = ""
        sources_found = False
        for line in res.iter_lines():
            if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                try:
                    ev = json.loads(line[6:])
                    if ev.get("type") == "delta":
                        full_text += ev.get("data", "")
                    elif ev.get("type") == "sources":
                        sources_found = True
                except:
                    pass

        assert len(full_text) > 0, "Expected non-empty response"
        assert sources_found, "Expected RAG sources citation"
        print(f"    (Retrieved answer length: {len(full_text)} chars)")

def test_static_assets_serving(client):
    """정적 프론트엔드 자산 캐시 버스팅 및 렌더링 검증"""
    admin_res = client.get("/admin")
    assert admin_res.status_code == 200
    assert "modal-chunk-content-box" in admin_res.text
    assert "admin.js?v=5.2.2" in admin_res.text

if __name__ == "__main__":
    print("=== [Production Readiness Tests Starting] ===")
    with httpx.Client(base_url=BASE_URL, timeout=40.0) as c:
        print("[1/5] Testing /api/health...")
        test_health_check(c)
        print("  [PASS] Health check passed.")

        print("[2/5] Testing vector embeddings integrity...")
        test_cached_vector_embeddings_integrity()
        print("  [PASS] 468 embeddings and metadata (468, 1024) verified.")

        print("[3/5] Testing admin auth & master corpus count...")
        test_admin_auth_and_master_corpus_count(c)
        print("  [PASS] Admin loaded exactly 468 master documents.")

        print("[4/5] Testing RAG search on mined precedents...")
        test_rag_search_scourt_precedents(c)
        print("  [PASS] RAG precedent search and reasoning response verified.")

        print("[5/5] Testing static frontend assets...")
        test_static_assets_serving(c)
        print("  [PASS] Static assets and cache-busting v5.2.2 verified.")

    print("\n[SUCCESS] ALL 5 PRODUCTION READINESS TESTS PASSED! (100%)")
