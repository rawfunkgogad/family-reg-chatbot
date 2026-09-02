import re

def linkify_law_text(text: str) -> str:
    # 1. Articles with Law Name
    patterns = [
        (
            r'(「?(?:가족관계의\s*등록\s*등에\s*관한\s*법률|가족관계등록법)」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/가족관계의등록등에관한법률/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?(?:가족관계의\s*등록\s*등에\s*관한\s*규칙|가족관계등록규칙)」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/가족관계의등록등에관한규칙/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?민법」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/민법/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?주민등록법」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/주민등록법/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?국제사법」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/국제사법/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?국적법」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/국적법/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(「?비송사건절차법」?)\s*(제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/비송사건절차법/(\2)" target="_blank" class="law-link-badge" title="국가법령정보센터 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 \2 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(?<![가-힣])(법\s*제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/가족관계의등록등에관한법률/(\1)" target="_blank" class="law-link-badge" title="국가법령정보센터 가족관계등록법 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(?<![가-힣])(규칙\s*제\d+(?:조의\d+)?조(?:\s*제\d+항)?)',
            r'<a href="https://www.law.go.kr/법령/가족관계의등록등에관한규칙/(\1)" target="_blank" class="law-link-badge" title="국가법령정보센터 가족관계등록규칙 바로가기"><i class="fa-solid fa-scale-balanced"></i> \1 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
        (
            r'(대법원\s*가족관계등록예규\s*제\d+호|예규\s*제\d+호)',
            r'<a href="https://www.law.go.kr/행정규칙/가족관계의등록등에관한예규" target="_blank" class="law-link-badge directive" title="국가법령정보센터 대법원 행정예규 바로가기"><i class="fa-solid fa-book"></i> \1 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>'
        ),
    ]

    result = text
    for pat, repl in patterns:
        result = re.sub(pat, repl, result)
    return result

# Test sample
sample_text = """
1. 가족관계의 등록 등에 관한 법률 제18조 제2항에 따라 간이직권정정이 가능합니다.
2. 규칙 제60조 및 예규 제543호를 확인하세요.
3. 민법 제844조에 따라 친생추정이 됩니다.
4. 법 제14조에 따라 형제자매 청구가 제한됩니다.
"""

print(linkify_law_text(sample_text))
