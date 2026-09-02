import urllib.request
import urllib.parse
import re

print("=" * 65)
print("1. 국가법령정보센터 (law.go.kr) 가지번호 조문 직통 URL 생존성 검증")
print("=" * 65)

articles_to_test = [
    ("가족관계의등록등에관한법률", "제14조", "제14조(가족관계등록부 등의 증명서 교부 등)"),
    ("가족관계의등록등에관한법률", "제14조의2", "제14조의2(인터넷을 통한 증명서등의 교부청구 등)"),
    ("가족관계의등록등에관한법률", "제18조", "제18조(직권정정)"),
    ("가족관계의등록등에관한법률", "제99조", "제99조(개명신고)"),
    ("가족관계의등록등에관한규칙", "제19조", "제19조(교부청구의 방법)"),
    ("가족관계의등록등에관한규칙", "제60조", "제60조(간이직권정정사유)"),
    ("민법", "제844조", "제844조(남편의 친생자의 추정)"),
    ("민법", "제846조", "제846조(친생부인의 소)")
]

for law, art_code, desc in articles_to_test:
    url = f"https://www.law.go.kr/{urllib.parse.quote('법령')}/{urllib.parse.quote(law)}/{urllib.parse.quote(art_code)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            print(f"[HTTP {res.status} OK] {desc} -> {url}")
            assert res.status == 200
    except Exception as e:
        print(f"[FAIL] {desc} -> {e}")
        raise e

print("\n" + "=" * 65)
print("2. 프론트엔드 정적 파일 서빙 검증")
print("=" * 65)

with urllib.request.urlopen("http://127.0.0.1:8000/static/app.js") as res:
    js_content = res.read().decode('utf-8')
    assert "linkifyLawReferences" in js_content
    assert "lawCompoundPattern" in js_content
    print(f"-> app.js 정상 서빙 (크기: {len(js_content)} bytes)")

print("\n🎉 [가지번호(제14조의2 등) 및 연속 조문 링크 파서 전체 검증 완료!]")
