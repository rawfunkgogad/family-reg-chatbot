import urllib.request
import urllib.parse
import ssl
import json
import time
from typing import Dict, Any, List, Optional

class OpenLawAPI:
    """
    국가법령정보 공동활용(open.law.go.kr) Open API 클라이언트
    """
    BASE_URL = "https://www.law.go.kr/DRF"
    
    def __init__(self, oc: str = "familylawapi", delay_sec: float = 0.15, timeout_sec: int = 15):
        self.oc = oc
        self.delay_sec = delay_sec
        self.timeout_sec = timeout_sec
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def _get_json(self, service: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        params["OC"] = self.oc
        params["type"] = "JSON"
        query_str = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/{service}?{query_str}"
        
        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(self.delay_sec)
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout_sec) as res:
                    body = res.read().decode('utf-8')
                    return json.loads(body)
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(f"Open API request failed ({url}): {e}")
                time.sleep(attempt * 1.0)

    def get_law_hierarchy(self, mst: int = 257203) -> Dict[str, Any]:
        """
        법령체계도 조회 (target=lsStmd)
        - 기본정보, 상하위법령, 관련법령(특례법 등), 위임 행정규칙 정보 반환
        """
        return self._get_json("lawService.do", {"target": "lsStmd", "MST": mst})

    def get_law_detail(self, mst: int) -> Dict[str, Any]:
        """
        법령 본문 상세 조회 (target=law)
        - 조문단위, 부칙, 제개정이유, 기본정보 등
        """
        return self._get_json("lawService.do", {"target": "law", "MST": mst})

    def get_admrul_detail(self, adm_id: str) -> Dict[str, Any]:
        """
        행정규칙 본문 상세 조회 (target=admrul)
        """
        return self._get_json("lawService.do", {"target": "admrul", "ID": adm_id})

    def search_law(self, query: str) -> Dict[str, Any]:
        """
        법령 검색 (target=law)
        """
        return self._get_json("lawSearch.do", {"target": "law", "query": query})
