# Korean Profanity, Abusive Language, and Prompt Injection Patterns

PROFANITY_KEYWORDS = {
    # 욕설 및 비속어
    "시발", "씨발", "시팔", "씨팔", "씨바", "시바", "ㅅㅂ", "ㅆㅂ",
    "개새끼", "개색기", "개새키", "개쉐이", "개색", "개섹", "ㄱㅅㄲ",
    "병신", "븅신", "병쉰", "ㅂㅅ", "호구",
    "지랄", "ㅈㄹ", "지럴",
    "좆", "존나", "졸라", "좃", "ㅈㄴ",
    "씹", "씹새", "씹덕", "씹창", "쌉",
    "닥쳐", "꺼져", "꺼지셈", "뒤져", "뒈져", "디져", "죽어라", "죽어버려",
    "미친놈", "미친년", "미친자", "미친새끼", "ㅁㅊ",
    "염병", "옘병", "엠병",
    "새끼", "새키", "세끼",
    "창녀", "걸레", "보지", "자지", "섹스", "자위", "섹스해",
    "느금마", "니애미", "느개비", "니애비", "패드립",
    "대가리", "대가리박아", "대가리깨",
    "애미", "애비"
}

# Prompt Injection & Jailbreak Attempt Patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|above)\s+instructions",
    r"you\s+are\s+now\s+(a|an|in|the)\s+dan\s+mode",
    r"jailbreak",
    r"system\s+prompt\s*(show|display|reveal|print|tell|output)",
    r"시스템\s*프롬프트(를|가)?\s*(알려|출력|보여|말해|공개)",
    r"(이전|기존)\s*(모든\s*)?(지침|명령|프롬프트|규칙)(을|를)?\s*(무시|잊어|취소|삭제)",
    r"비밀번호(를|가)?\s*(알려|말해|출력)",
    r"관리자\s*권한(을|으로)?\s*(획득|부여|해제)",
    r"탈옥\s*(모드|실행|해줘)"
]
