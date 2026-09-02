import asyncio
import sys
import re
import urllib.parse
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from llm_client import stream_chat_completion

def linkify_law_references(html: str) -> str:
    def build_law_url(canon_law: str, article_raw: str) -> str:
        art_anchor = ""
        if article_raw:
            art_match = re.search(r'제\d+(?:조의\d+)?조', article_raw)
            if art_match:
                art_anchor = f"({art_match.group(0)})"
        encoded_law = urllib.parse.quote(canon_law)
        encoded_art = urllib.parse.quote(art_anchor) if art_anchor else ""
        return f"https://www.law.go.kr/법령/{encoded_law}/{encoded_art}" if encoded_art else f"https://www.law.go.kr/법령/{encoded_law}"

    # 1. Specific Laws with Articles
    def repl_specific(m):
        law_name = m.group(2)
        article = m.group(3)
        clean_law = re.sub(r'[「」\s]', '', law_name)
        lookup = "가족관계의등록등에관한법률"
        if "규칙" in clean_law: lookup = "가족관계의등록등에관한규칙"
        elif "민법" in clean_law: lookup = "민법"
        elif "주민등록" in clean_law: lookup = "주민등록법"
        elif "국제사법" in clean_law: lookup = "국제사법"
        elif "국적법" in clean_law: lookup = "국적법"
        elif "비송" in clean_law: lookup = "비송사건절차법"
        
        url = build_law_url(lookup, article)
        return f'<a href="{url}" target="_blank" class="law-link-badge"><i class="fa-solid fa-scale-balanced"></i> {m.group(0)}</a>'

    out = re.sub(
        r'(「?(가족관계의\s*등록\s*등에\s*관한\s*법률|가족관계등록법|가족관계의\s*등록\s*등에\s*관한\s*규칙|가족관계등록규칙|민법|주민등록법|국제사법|국적법|비송사건절차법)」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?(?:\s*제\d+호)?)',
        repl_specific,
        html
    )

    # 2. Short forms
    out = re.sub(
        r'(?<![가-힣a-zA-Z0-9_\/])(법)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?(?:\s*제\d+호)?)',
        lambda m: f'<a href="{build_law_url("가족관계의등록등에관한법률", m.group(2))}" target="_blank" class="law-link-badge"><i class="fa-solid fa-scale-balanced"></i> {m.group(0)}</a>',
        out
    )

    out = re.sub(
        r'(?<![가-힣a-zA-Z0-9_\/])(규칙)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?(?:\s*제\d+호)?)',
        lambda m: f'<a href="{build_law_url("가족관계의등록등에관한규칙", m.group(2))}" target="_blank" class="law-link-badge"><i class="fa-solid fa-scale-balanced"></i> {m.group(0)}</a>',
        out
    )

    return out

async def test_law_linking_flow():
    print("=" * 65)
    print("국가법령정보센터 자동 링크 변환 파이프라인 검증")
    print("=" * 65)

    test_queries = [
        "형제자매 가족관계증명서 발급 청구 제한 관련 법률 조항",
        "전산오기 직권정정 요건 및 규칙 조항"
    ]

    for q in test_queries:
        print(f"\n[질의]: {q}")
        messages = [{"role": "user", "content": q}]
        response_text = ""
        async for chunk in stream_chat_completion(messages, mode="official", model="llama-3.3-70b"):
            if chunk["type"] == "delta":
                response_text += chunk["data"]

        linked_html = linkify_law_references(response_text)
        
        # Check if law.go.kr links are generated
        law_links = re.findall(r'href="(https://www.law.go.kr/[^"]+)"', linked_html)
        print(f"-> 생성된 답변 내 국가법령정보센터 직통 링크 ({len(law_links)}개):")
        for l in law_links[:4]:
            print(f"   🔗 {urllib.parse.unquote(l)}")
        
        assert len(law_links) > 0, "국가법령정보센터 링크가 최소 1개 이상 생성되어야 합니다."

    print("\n🎉 [국가법령정보센터 조문 직통 링크 자동 생성 검증 성공!]")

if __name__ == "__main__":
    asyncio.run(test_law_linking_flow())
