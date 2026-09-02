import httpx
import asyncio
import json

API_KEY = "sk-dev-Un5B6gafFJxVcRwGnw5AlT23wDGn1ooA"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

async def test_capabilities():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Test Embeddings (bge-m3)
        print("--- 1. Testing Embeddings (bge-m3) ---")
        try:
            embed_res = await client.post(
                "https://open.hasa.re.kr/v1/embeddings",
                headers=HEADERS,
                json={
                    "model": "bge-m3",
                    "input": "가족관계등록법 제18조 직권정정"
                }
            )
            print(f"Status: {embed_res.status_code}")
            if embed_res.status_code == 200:
                data = embed_res.json()
                embedding = data["data"][0]["embedding"]
                print(f"Embedding success! Vector dim: {len(embedding)}")
            else:
                print(f"Embedding error: {embed_res.text}")
        except Exception as e:
            print(f"Embedding exception: {e}")

        # 2. Test Rerank (bge-reranker-v2-m3)
        print("\n--- 2. Testing Rerank (bge-reranker-v2-m3) ---")
        try:
            rerank_res = await client.post(
                "https://open.hasa.re.kr/rerank",
                headers=HEADERS,
                json={
                    "model": "bge-reranker-v2-m3",
                    "query": "간이직권정정 대상",
                    "documents": [
                        "가족관계등록법 제18조 제2항 및 규칙 제60조는 경미한 오기를 감독법원 허가 없이 직권정정할 수 있도록 규정한다.",
                        "협의이혼은 확인서등본 교부 후 3개월 이내에 신고해야 한다.",
                        "출생신고는 1개월 이내에 하여야 한다."
                    ]
                }
            )
            print(f"Status: {rerank_res.status_code}")
            if rerank_res.status_code == 200:
                data = rerank_res.json()
                print(f"Rerank success! Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                # Let's also check if /v1/rerank or rerank works
                print(f"Rerank error at /rerank: {rerank_res.text}")
                v1_rerank = await client.post(
                    "https://open.hasa.re.kr/v1/rerank",
                    headers=HEADERS,
                    json={
                        "model": "bge-reranker-v2-m3",
                        "query": "간이직권정정 대상",
                        "documents": [
                            "가족관계등록법 제18조 제2항 및 규칙 제60조는 경미한 오기를 감독법원 허가 없이 직권정정할 수 있도록 규정한다.",
                            "협의이혼은 확인서등본 교부 후 3개월 이내에 신고해야 한다."
                        ]
                    }
                )
                print(f"Retry at /v1/rerank: {v1_rerank.status_code}, {v1_rerank.text}")
        except Exception as e:
            print(f"Rerank exception: {e}")

        # 3. Test Agent Chat (web search agent)
        print("\n--- 3. Testing Agent Chat (/v1/agent/chat) ---")
        try:
            agent_res = await client.post(
                "https://open.hasa.re.kr/v1/agent/chat",
                headers=HEADERS,
                json={
                    "model": "qwen3-coder",
                    "messages": [{"role": "user", "content": "대법원 가족관계등록예규 최신 소식 알려줘"}]
                }
            )
            print(f"Status: {agent_res.status_code}")
            if agent_res.status_code == 200:
                data = agent_res.json()
                print(f"Agent Chat success! Keys: {list(data.keys())}")
            else:
                print(f"Agent Chat response: {agent_res.text}")
        except Exception as e:
            print(f"Agent chat exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_capabilities())
