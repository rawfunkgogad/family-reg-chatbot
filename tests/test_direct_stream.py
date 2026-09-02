import httpx
import asyncio
import json

async def test_openai_direct():
    headers = {
        "Authorization": "Bearer sk-dev-Un5B6gafFJxVcRwGnw5AlT23wDGn1ooA",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "당신은 법률 전문가입니다."},
            {"role": "user", "content": "안녕하세요"}
        ],
        "temperature": 0.5,
        "max_tokens": 500,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post("https://open.hasa.re.kr/v1/chat/completions", headers=headers, json=payload)
        print("Non-stream Status:", res.status_code)
        print("Non-stream Response:", res.text[:300])

        # Test stream
        payload["stream"] = True
        print("\nTesting stream with httpx...")
        async with client.stream("POST", "https://open.hasa.re.kr/v1/chat/completions", headers=headers, json=payload) as stream_res:
            print("Stream Status:", stream_res.status_code)
            async for line in stream_res.aiter_lines():
                if line:
                    print("LINE:", line[:100])
                    break

if __name__ == "__main__":
    asyncio.run(test_openai_direct())
