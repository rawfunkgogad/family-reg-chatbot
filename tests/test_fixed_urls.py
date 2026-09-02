import urllib.request
import urllib.parse

def test_fixed_law_urls():
    test_cases = [
        ("가족관계의등록등에관한법률", "제95조"),
        ("가족관계의등록등에관한법률", "제14조"),
        ("가족관계의등록등에관한규칙", "제60조"),
        ("민법", "제844조"),
        ("주민등록법", "제29조"),
        ("국적법", "제9조"),
    ]

    print("=" * 65)
    print("국가법령정보센터 조문 직통 URL 정밀 검증 (오류 없음 확인)")
    print("=" * 65)

    for law, art in test_cases:
        path = f"/법령/{law}/{art}"
        encoded_path = urllib.parse.quote(path)
        url = f"https://www.law.go.kr{encoded_path}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5)
        body = res.read().decode('utf-8', errors='ignore')
        is_error = '해당 한글주소명을 찾을 수 없습니다' in body
        print(f"🔗 {law} {art} -> {url}")
        print(f"   결과: {'❌ 오류 발생' if is_error else '✅ 정상 조문 이동 확인 (Status: 200)'}")
        assert not is_error, f"URL failed: {url}"

    print("\n🎉 모든 국가법령정보센터 조문 직통 링크가 정상 작동합니다!")

if __name__ == "__main__":
    test_fixed_law_urls()
