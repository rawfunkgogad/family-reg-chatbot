import urllib.request
import urllib.error
import ssl
import json
import time
from typing import Dict, Any, Optional, List

class ScourtAPIClient:
    """
    대법원 사법정보공개포털(portal.scourt.go.kr) REST JSON API 클라이언트
    """
    BASE_URL = "https://portal.scourt.go.kr"
    
    def __init__(self, delay_sec: float = 0.2, timeout_sec: int = 15):
        self.delay_sec = delay_sec
        self.timeout_sec = timeout_sec
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json; charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Origin': self.BASE_URL,
            'Referer': f'{self.BASE_URL}/pgp/index.on?m=PGP1051M01&l=N&c=900'
        }
    
    def _request(self, endpoint: str, payload: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        data = json.dumps(payload).encode('utf-8')
        
        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(self.delay_sec)
                req = urllib.request.Request(url, data=data, headers=self.headers)
                with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout_sec) as res:
                    body = res.read().decode('utf-8')
                    return json.loads(body)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                if attempt == max_retries:
                    raise RuntimeError(f"Failed request to {url} after {max_retries} attempts: {e}")
                time.sleep(attempt * 1.0)
    
    def get_directory_tree(self, dirc_dvs_cd: str) -> List[Dict[str, Any]]:
        """
        디렉토리 계층 트리 조회
        - dirc_dvs_cd: '705' (가족관계등록예규), '709' (가족관계등록선례)
        """
        payload = {
            "dma_lwTrmParam": {
                "jisCntntsDircSeq": "",
                "jisCntntsDircDvsCd": dirc_dvs_cd,
                "uprJisCntntsDircSeq": 0,
                "cntntsDircLvl": ""
            }
        }
        res = self._request("/pgp/pgp1002/selectLwTrmLst.on", payload)
        return res.get("data", {}).get("dlt_lwTrmLst", [])
    
    def get_document_list(
        self,
        cl_ctt: str,
        current_only: bool = True,
        page_no: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        문서 목록 조회 (페이징 지원)
        - cl_ctt: 'FR' (가족관계등록예규), 'FP' (가족관계등록선례)
        - current_only: True (현행만), False (전체)
        """
        payload = {
            "dma_searchParam02": {
                "category": "ruleEstbrlPrcdt",
                "orderBy": "ESTBRL_DATA_NO ASC",
                "estbrlClCtt": cl_ctt,
                "crntEstbrlYn": "Y" if current_only else "",
                "pageNo": page_no,
                "pageSize": page_size,
                "totalYn": "Y" if page_no == 1 else "N",
                "totalCnt": 0
            }
        }
        res = self._request("/pgp/pgp1051/selectRuleEstbrlPrcdtDircLst.on", payload)
        data = res.get("data", {})
        return {
            "items": data.get("dlt_ruleEstbrlPrcdtLst", []),
            "page_info": data.get("dma_pageInfo", {})
        }
    
    def get_base_info(self, jis_cntnts_srno: int) -> Dict[str, Any]:
        """
        상세 기본 메타정보 조회
        """
        payload = {
            "dma_searchParam": {
                "jisCntntsSrno": jis_cntnts_srno
            }
        }
        res = self._request("/pgp/pgp1051/selectRuleEstbrlPrcdtBasInf.on", payload)
        return res.get("data", {}).get("dma_ruleEstbrlPrcdtBasInf", {})
    
    def get_context(self, jis_cntnts_srno: int, knd_cd: Optional[str] = None) -> Dict[str, Any]:
        """
        본문 컨텍스트 (HTML / xsltDocument) 조회
        """
        payload = {
            "dma_searchParam02": {
                "docType": "bMun",
                "jisCntntsSrno": jis_cntnts_srno,
                "jisCntntsKndCd": knd_cd or "",
                "chnchrYn": "N"
            }
        }
        res = self._request("/pgp/pgp1051/selectRuleEstbrlPrcdtCtxt.on", payload)
        return res.get("data", {}).get("dma_ruleEstbrlPrcdtCtxt", {})
