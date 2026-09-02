import urllib.request
import urllib.parse
import json

print("=" * 65)
print("1. /api/chat에 bypass_cache=True 전송 검증")
print("=" * 65)

payload = {
    "messages": [{"role": "user", "content": "인터넷 출생신고 참여병원 확인 방법"}],
    "temperature": 0.5,
    "max_tokens": 800,
    "use_rag": True,
    "use_web_search": False,
    "mode": "unified",
    "model": "llama-3.3-70b",
    "bypass_cache": True
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/chat",
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as res:
    print(f"-> 응답 상태코드: {res.status}")
    assert res.status == 200
    text = res.read().decode('utf-8')
    assert "data:" in text
    assert "[DONE]" in text
    print(f"-> 실시간 스트리밍 바이트 수: {len(text)} bytes")

print("\n" + "=" * 65)
print("2. app.js 정적 파일 내 regenerateAnswer 및 파라미터 무결성 검증")
print("=" * 65)

with urllib.request.urlopen("http://127.0.0.1:8000/static/app.js") as res:
    js = res.read().decode('utf-8')
    assert "lastUserQuery" in js
    assert "function addAssistantActions(messageRow, textContent, metrics, userQuery, isCached)" in js
    assert "regenerateAnswer" in js
    print("-> addAssistantActions 및 regenerateAnswer 시그니처 일치 확인 완료!")

print("\n🎉 [새 답변 재생성 액션 및 실시간 AI 호출 파이프라인 전체 검증 완료!]")
