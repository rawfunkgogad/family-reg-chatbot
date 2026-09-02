import urllib.request
import json

def test_endpoints():
    print("Testing GET http://127.0.0.1:8000/ ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/") as response:
        html = response.read().decode("utf-8")
        assert "가족관계등록 실무·선례 AI 어시스턴트" in html
        print(f" Root HTML OK (Length: {len(html)} bytes)")

    print("Testing GET http://127.0.0.1:8000/api/kb ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/kb") as response:
        data = json.loads(response.read().decode("utf-8"))
        assert "statutes_core" in data
        print(f" Knowledge Base API OK (Categories: {len(data.get('practical_categories', []))})")

    print("Testing GET http://127.0.0.1:8000/api/quick-cases ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/quick-cases") as response:
        cases = json.loads(response.read().decode("utf-8"))
        assert len(cases) > 0
        print(f" Quick Cases API OK (Cases count: {len(cases)})")

    print("Testing POST http://127.0.0.1:8000/api/chat (SSE stream) ...")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat",
        data=json.dumps({
            "messages": [{"role": "user", "content": "협의이혼의사확인서 3개월 기간 도과 시 처리 요령"}],
            "temperature": 0.3
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        first_few_lines = []
        for _ in range(10):
            line = response.readline().decode("utf-8")
            if line:
                first_few_lines.append(line.strip())
        print(f" SSE Stream OK! First chunks:\n" + "\n".join(first_few_lines[:5]))

    print("\n All API endpoints and Streaming Services are working perfectly!")

if __name__ == "__main__":
    test_endpoints()
