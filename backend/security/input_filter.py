import re
import time
from typing import Dict, Any, List, Tuple
from .profanity_dict import PROFANITY_KEYWORDS, PROMPT_INJECTION_PATTERNS

class InputFilter:
    """
    개인식별정보(PII) 자동 탐지 및 마스킹,
    비속어·욕설 및 프롬프트 인젝션 실시간 가드레일 시스템
    """
    def __init__(self):
        # 통계 카운터
        self.stats = {
            "total_checked": 0,
            "pii_masked_count": 0,
            "inappropriate_blocked_count": 0,
            "pii_type_counts": {
                "rrn": 0,          # 주민등록번호 / 외국인등록번호
                "phone": 0,        # 전화번호
                "card": 0,         # 신용카드번호
                "account": 0,      # 계좌번호
                "email": 0,        # 이메일
                "passport": 0,     # 여권번호
                "driver_license": 0# 운전면허번호
            },
            "last_incident_time": None
        }

        # 정규표현식 컴파일
        self.re_rrn = re.compile(r"(?<!\d)(\d{6})[-.\s]?([1-8])(?:\d{6}|\*{6})(?!\d)")
        self.re_mobile = re.compile(r"(?<!\d)(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)")
        self.re_tel = re.compile(r"(?<!\d)(02|0[3-6]\d|070|050\d?)[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)")
        self.re_card = re.compile(r"(?<!\d)(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{3,4}(?!\d)")
        self.re_email = re.compile(r"\b([A-Za-z0-9._%+-]{1,2})([A-Za-z0-9._%+-]*?)@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b")
        self.re_passport = re.compile(r"\b([A-Z]{1,2})\d{7,8}\b")
        self.re_driver = re.compile(r"\b(\d{2})[-.\s]?(\d{2})[-.\s]?(\d{6})[-.\s]?(\d{2})\b")
        
        # 프롬프트 인젝션 패턴 컴파일
        self.injection_regexes = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]

    def detect_privacy_info(self, text: str) -> Dict[str, Any]:
        """
        텍스트 내 개인정보를 탐지하고 안전하게 마스킹한 텍스트를 반환합니다.
        """
        if not text:
            return {"has_pii": False, "sanitized_text": "", "detected_types": []}

        detected_types = []
        sanitized = text

        # 1. 주민등록번호 / 외국인등록번호 (900101-1234567 -> 900101-1******)
        if self.re_rrn.search(sanitized):
            detected_types.append("주민등록번호/외국인번호")
            sanitized = self.re_rrn.sub(r"\1-\2******", sanitized)
            self.stats["pii_type_counts"]["rrn"] += 1

        # 2. 휴대전화번호 (010-1234-5678 -> 010-****-5678)
        if self.re_mobile.search(sanitized):
            detected_types.append("휴대전화번호")
            sanitized = self.re_mobile.sub(r"\1-****-\3", sanitized)
            self.stats["pii_type_counts"]["phone"] += 1

        # 3. 일반 유선전화번호 (02-1234-5678 -> 02-****-5678)
        if self.re_tel.search(sanitized):
            if "전화번호" not in [d.split("/")[0] for d in detected_types]:
                detected_types.append("일반전화번호")
            sanitized = self.re_tel.sub(r"\1-****-\3", sanitized)
            self.stats["pii_type_counts"]["phone"] += 1

        # 4. 신용카드번호
        if self.re_card.search(sanitized):
            detected_types.append("신용카드번호")
            sanitized = self.re_card.sub("[카드번호 마스킹됨]", sanitized)
            self.stats["pii_type_counts"]["card"] += 1

        # 5. 운전면허번호
        if self.re_driver.search(sanitized):
            detected_types.append("운전면허번호")
            sanitized = self.re_driver.sub(r"\1-**-******-**", sanitized)
            self.stats["pii_type_counts"]["driver_license"] += 1

        # 6. 여권번호 (가족관계 법령 조문 번호와 충돌 방지: 예: M12345678)
        if self.re_passport.search(sanitized):
            # 문맥상 조문('제OO조')이 아닌 영문 여권 번호 패턴
            detected_types.append("여권번호")
            sanitized = self.re_passport.sub(r"\1*******", sanitized)
            self.stats["pii_type_counts"]["passport"] += 1

        # 7. 이메일 주소 (hong@example.com -> ho***@example.com)
        if self.re_email.search(sanitized):
            detected_types.append("이메일주소")
            sanitized = self.re_email.sub(r"\1***@\3", sanitized)
            self.stats["pii_type_counts"]["email"] += 1

        has_pii = len(detected_types) > 0
        if has_pii:
            self.stats["pii_masked_count"] += 1
            self.stats["last_incident_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "has_pii": has_pii,
            "detected_types": list(set(detected_types)),
            "sanitized_text": sanitized,
            "original_text": text
        }

    def detect_inappropriate_content(self, text: str) -> Dict[str, Any]:
        """
        비속어, 욕설, 혐오 표현 및 프롬프트 인젝션 시도를 탐지합니다.
        """
        if not text:
            return {"is_inappropriate": False, "category": "NONE", "message": ""}

        # 1. 프롬프트 인젝션 탐지
        for reg in self.injection_regexes:
            if reg.search(text):
                self.stats["inappropriate_blocked_count"] += 1
                self.stats["last_incident_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                return {
                    "is_inappropriate": True,
                    "category": "INJECTION",
                    "reason": "시스템 보안 지침 우회 시도",
                    "message": "⚠️ **[보안 안내]** 시스템 지침 변경 또는 보안 규칙 우회 질의는 처리가 제한됩니다. 대한민국 법원 가족관계등록 관련 정상적인 업무 문의를 입력해 주시기 바랍니다."
                }

        # 2. 비속어 및 욕설 탐지
        # 공백 제거 텍스트로도 검사하여 자모 분리나 띄어쓰기 우회 방지
        compact_text = text.replace(" ", "").lower()
        for bad_word in PROFANITY_KEYWORDS:
            if bad_word in compact_text:
                self.stats["inappropriate_blocked_count"] += 1
                self.stats["last_incident_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                return {
                    "is_inappropriate": True,
                    "category": "PROFANITY",
                    "reason": "비속어 및 부적절한 언어 사용",
                    "message": "⚠️ **[이용 안내]** 건전하고 신뢰할 수 있는 상담 환경을 위해 욕설, 비속어 또는 공격적인 표현이 포함된 입력은 처리할 수 없습니다. 가족관계등록 관련 문의사항을 다시 입력해 주시기 바랍니다."
                }

        return {
            "is_inappropriate": False,
            "category": "NONE",
            "message": ""
        }

    def strip_privacy_info(self, text: str) -> str:
        """
        입력 텍스트에서 개인정보(주민번호, 전화번호, 카드번호 등)를 안전하게 마스킹/정리하여 반환합니다.
        """
        res = self.detect_privacy_info(text)
        return res["sanitized_text"]

    def validate_and_sanitize(self, text: str, strict_block_pii: bool = True) -> Dict[str, Any]:
        """
        사용자 입력에 대한 통합 검증을 수행합니다.
        strict_block_pii=True 인 경우 개인정보 발견 시 전송을 원천 차단합니다.
        """
        self.stats["total_checked"] += 1

        # 1. 부적절한 입력 검사 (비속어 / 프롬프트 인젝션)
        inappropriate_res = self.detect_inappropriate_content(text)
        if inappropriate_res["is_inappropriate"]:
            return {
                "allowed": False,
                "sanitized_text": "",
                "inappropriate": inappropriate_res,
                "pii": {"has_pii": False, "detected_types": []}
            }

        # 2. 개인정보 탐지
        pii_res = self.detect_privacy_info(text)

        # 3. 개인정보 입력 원천 차단 정책 (Strict PII Blocking)
        if strict_block_pii and pii_res["has_pii"]:
            types_str = ", ".join(pii_res["detected_types"])
            self.stats["inappropriate_blocked_count"] += 1
            return {
                "allowed": False,
                "sanitized_text": pii_res["sanitized_text"],
                "inappropriate": {
                    "is_inappropriate": True,
                    "category": "PII_BLOCKED",
                    "reason": f"개인식별정보({types_str}) 입력 원천 차단",
                    "message": f"❌ **[개인정보 입력 원천 차단 안내]**\n\n입력하신 내용에 **{types_str}**이 포함되어 있어 개인정보보호법에 따라 전송이 차단되었습니다.\n\n개인정보(주민번호, 전화번호, 카드번호 등)를 삭제하신 후 일반적인 법률 요건 및 절차 내용을 문의해 주시기 바랍니다."
                },
                "pii": pii_res
            }

        return {
            "allowed": True,
            "sanitized_text": pii_res["sanitized_text"],
            "inappropriate": inappropriate_res,
            "pii": pii_res
        }

    def get_stats(self) -> Dict[str, Any]:
        """필터링 및 마스킹 통계 반환"""
        return self.stats

    def reset_stats(self):
        """통계 초기화"""
        self.stats["total_checked"] = 0
        self.stats["pii_masked_count"] = 0
        self.stats["inappropriate_blocked_count"] = 0
        for k in self.stats["pii_type_counts"]:
            self.stats["pii_type_counts"][k] = 0

# Global Singleton Instance
input_filter = InputFilter()
