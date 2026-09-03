"""
대법원 예규/선례 인앱 원문 뷰어 및 스마트 링크 리졸버 검증 테스트
"""
import httpx
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def test_directive_626_lookup():
    """가족관계등록예규 제626호 실시간 원문 및 스마트 링크 검증"""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        res = client.get("/api/legal/document", params={"query": "가족관계등록예규 제626호"})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert data["found"] is True, "Document should be found"
        assert data["id"] == "SCOURT-DIR-626", f"Expected SCOURT-DIR-626, got {data['id']}"
        assert "혼인신고수리불가신고서" in data["clean_title"]
        assert len(data["content"]) > 2000, "Content should be full text (>2000 chars)"
        
        # 국가법령정보센터 링크에 발령번호가 아닌 실제 규칙 명칭 키워드가 포함되었는지 확인
        decoded_law_url = urllib.parse.unquote(data["law_go_kr_url"])
        assert "혼인신고수리불가" in decoded_law_url, f"Expected clean rule title in law url, got {decoded_law_url}"
        print(f"  [PASS] Directive 626 verified: {data['title'][:40]}... (Content: {len(data['content'])} chars)")

def test_precedent_lookup():
    """가족관계등록선례 제200805-7호 실시간 원문 및 스마트 링크 검증"""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        res = client.get("/api/legal/document", params={"query": "가족관계등록선례 제200805-7호"})
        assert res.status_code == 200
        data = res.json()
        assert data["found"] is True
        assert data["id"] == "SCOURT-PREC-200805-7"
        assert "귀화" in data["clean_title"]
        assert len(data["content"]) > 500
        print(f"  [PASS] Precedent 200805-7 verified: {data['title'][:40]}... (Content: {len(data['content'])} chars)")

def test_frontend_assets_integration():
    """프론트엔드 모달 UI 및 인앱 뷰어 자산 통합 검증"""
    index_path = Path("frontend/index.html")
    app_js_path = Path("frontend/app.js")
    style_path = Path("frontend/style.css")

    with open(index_path, encoding="utf-8") as f:
        html = f.read()
    assert 'id="legalDocModal"' in html, "legalDocModal markup missing in index.html"
    assert 'app.js?v=5.3.1' in html, "app.js cache busting v5.3.1 missing"

    with open(app_js_path, encoding="utf-8") as f:
        js = f.read()
    assert "openLegalDocModal" in js, "openLegalDocModal missing in app.js"
    assert "in-app-viewer" in js, "in-app-viewer class missing in app.js"
    assert "국내입양에관한특별법" in js, "국내입양에관한특별법 canonical logic missing in app.js"
    assert "국제입양에관한법률" in js, "국제입양에관한법률 canonical logic missing in app.js"

    with open(style_path, encoding="utf-8") as f:
        css = f.read()
    assert ".legal-doc-modal-card" in css, "legal-doc-modal-card styles missing in style.css"
    assert '[data-theme="light"] .legal-doc-modal-card' in css, "Light theme styles missing in style.css"
    print("  [PASS] Frontend modal, styles, and event handlers verified.")

def test_special_adoption_laws_linking_with_node():
    """Node.js 환경에서 사용자의 실제 발화(국내입양특별법, 국제입양법 연속 조문) 파싱 무결성 검증"""
    import subprocess
    cmd = ["node", "tests/test_law_regex.js"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"Node execution failed: {res.stderr}"
    out = urllib.parse.unquote(res.stdout)
    assert "국내입양에관한특별법/제21조" in out
    assert "국제입양에관한법률/제12조" in out
    assert "국제입양에관한법률/제22조" in out
    assert "국제입양에관한법률/제23조" in out
    print("  [PASS] Adoption special laws (국내/국제입양) and consecutive articles linkified perfectly.")

if __name__ == "__main__":
    print("=== [Testing Supreme Court Legal Doc In-App Viewer & Smart Linker] ===")
    test_directive_626_lookup()
    test_precedent_lookup()
    test_frontend_assets_integration()
    test_special_adoption_laws_linking_with_node()
    print("\n[SUCCESS] ALL LEGAL DOC & ADOPTION LAW TESTS PASSED! (100%)")
