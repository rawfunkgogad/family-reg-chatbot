import urllib.request
import json
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from security.input_filter import input_filter

def test_strict_blocking():
    print("=" * 65)
    print("1. 개인정보 원천 차단(Strict PII Blocking) 정책 검증")
    print("=" * 65)

    rrn_query = "주민번호 950101-1234567 인데 가족관계증명서 발급 가능한가요?"
    res = input_filter.validate_and_sanitize(rrn_query, strict_block_pii=True)
    
    print("-> 원문:", rrn_query)
    print("-> 허용 여부(allowed):", res["allowed"])
    print("-> 차단 사유:", res["inappropriate"]["reason"])
    print("-> 차단 안내문:\n", res["inappropriate"]["message"])

    assert res["allowed"] is False, "개인정보 포함 질의는 전송이 원천 차단되어야 합니다."
    assert "주민등록번호/외국인번호" in res["inappropriate"]["reason"]

    print("\n" + "=" * 65)
    print("2. /api/chat 엔드포인트 개인정보 원천 차단 SSE 응답 검증")
    print("=" * 65)

    chat_payload = {
        "messages": [{"role": "user", "content": "내 전화번호는 010-1234-5678 입니다."}],
        "mode": "unified",
        "bypass_cache": True
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat",
        data=json.dumps(chat_payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        sse_output = response.read().decode('utf-8')
        print("-> SSE 응답:\n", sse_output[:250])
        assert "security_block" in sse_output
        assert "개인정보 입력 원천 차단" in sse_output

    print("\n🎉 [개인정보 입력 원천 차단 가드레일 전체 검증 완료!]")

if __name__ == "__main__":
    test_strict_blocking()
