import urllib.request
import json
import sys
from pathlib import Path

def test_ab_prompt_system():
    print("=" * 65)
    print("1. 프롬프트 템플릿 목록 및 A/B 테스트 통계 API 검증")
    print("=" * 65)

    # 1. GET /api/prompts/templates
    with urllib.request.urlopen("http://127.0.0.1:8000/api/prompts/templates") as res:
        data = json.loads(res.read().decode('utf-8'))
        print("-> 등록된 프롬프트 템플릿 수:", len(data["templates"]))
        for t in data["templates"]:
            print(f"   [{t['id']}] {t['name']} (득표: {t['votes']}표, 승률: {t['win_rate_pct']}%, 활성: {t['is_active']})")
        assert len(data["templates"]) == 3

    print("\n" + "=" * 65)
    print("2. 사용자 선호도 투표 (A/B Preference Selection) API 검증")
    print("=" * 65)

    # 2. POST /api/prompts/select-preference (Vote for Template B)
    vote_payload = {"template_id": "B", "comment": "친절한 설명이 마음에 듭니다"}
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/prompts/select-preference",
        data=json.dumps(vote_payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        vote_res = json.loads(res.read().decode('utf-8'))
        print("-> 투표 결과:", vote_res)
        assert vote_res["success"] is True
        assert vote_res["active_template"] == "B"

    # 3. GET /api/prompts/ab-stats
    with urllib.request.urlopen("http://127.0.0.1:8000/api/prompts/ab-stats") as res:
        stats = json.loads(res.read().decode('utf-8'))
        print("-> A/B 테스팅 누적 통계:", stats)
        assert stats["total_votes"] >= 1
        assert stats["active_template"] == "B"

    print("\n" + "=" * 65)
    print("3. 템플릿별 실시간 LLM 답변 스타일 생성 검증 (A vs B)")
    print("=" * 65)

    # Test Chat with Template B (Friendly Conversational)
    chat_b_payload = {
        "messages": [{"role": "user", "content": "기본증명서 인터넷 발급 수수료가 얼마인가요?"}],
        "prompt_template": "B",
        "bypass_cache": True
    }
    req_b = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat",
        data=json.dumps(chat_b_payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_b) as res:
        sse_b = res.read().decode('utf-8')
        print("-> [템플릿 B - 대화형 친절 요약] SSE 응답:\n", sse_b[:260])
        assert len(sse_b) > 50

    print("\n🎉 [프롬프트 템플릿 A/B 테스팅 및 선호도 튜닝 시스템 전체 검증 성공!]")

if __name__ == "__main__":
    test_ab_prompt_system()
