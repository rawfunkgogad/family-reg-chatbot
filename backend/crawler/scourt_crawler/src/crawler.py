import os
import json
import time
from typing import Dict, Any, List, Optional, Callable
from .scourt_api import ScourtAPIClient
from .scourt_parser import parse_context_document, format_date

class ScourtCrawler:
    """
    대법원 가족관계등록예규 및 선례 자동 수집 및 변환 오케스트레이터
    """
    def __init__(self, client: Optional[ScourtAPIClient] = None, checkpoint_dir: Optional[str] = None):
        self.client = client or ScourtAPIClient()
        self.checkpoint_dir = checkpoint_dir
        if self.checkpoint_dir and not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir, exist_ok=True)
            
    def _build_dir_map(self, dirc_dvs_cd: str) -> Dict[str, str]:
        raw_tree = self.client.get_directory_tree(dirc_dvs_cd)
        dir_map = {}
        for item in raw_tree:
            code = item.get("ltrtClCtt")
            name = item.get("clTitlNm")
            if code and name:
                dir_map[code.strip()] = name.strip()
        return dir_map

    def _resolve_directory_path(self, cl_code: Optional[str], dir_map: Dict[str, str]) -> List[str]:
        if not cl_code:
            return []
        parts = cl_code.strip().split('-')
        path = []
        curr = ""
        for p in parts:
            curr = f"{curr}-{p}" if curr else p
            if curr in dir_map:
                name = dir_map[curr]
                # 인접한 동일 명칭 중복 방지 (예: 제1장 총칙 > 제1장 총칙)
                if not path or path[-1] != name:
                    path.append(name)
            else:
                # 'CP-99-2008' 같이 접두어가 살짝 다를 수 있는 경우 처리
                alt_curr = "CP-" + "-".join(parts[1:parts.index(p)+1])
                if alt_curr in dir_map:
                    name = dir_map[alt_curr]
                    if not path or path[-1] != name:
                        path.append(name)
        return path

    def crawl_dataset(
        self,
        target_type: str, # 'rules' 또는 'precedents'
        current_only: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        예규 또는 선례 데이터셋 일괄 수집
        - target_type: 'rules' (가족관계등록예규), 'precedents' (가족관계등록선례)
        """
        if target_type == 'rules':
            dirc_cd = "705"
            cl_ctt = "FR"
            cat_name = "가족관계등록예규"
        else:
            dirc_cd = "709"
            cl_ctt = "FP"
            cat_name = "가족관계등록선례"
            
        # 1. 디렉토리 트리 로드
        dir_map = self._build_dir_map(dirc_cd)
        
        # 2. 전체 목록 조회 (페이징 순회)
        all_items = []
        page_no = 1
        page_size = 100
        total_cnt = 0
        
        while True:
            resp = self.client.get_document_list(
                cl_ctt=cl_ctt,
                current_only=current_only,
                page_no=page_no,
                page_size=page_size
            )
            items = resp.get("items", [])
            page_info = resp.get("page_info", {})
            if page_no == 1:
                total_cnt = page_info.get("totalCnt", len(items))
            
            all_items.extend(items)
            if len(all_items) >= total_cnt or not items or len(items) < page_size:
                break
            page_no += 1

        # 3. 각 항목 상세 정보 및 본문 수집
        results = []
        checkpoint_file = None
        if self.checkpoint_dir:
            checkpoint_file = os.path.join(self.checkpoint_dir, f"{target_type}_checkpoint.json")
            if os.path.exists(checkpoint_file):
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        results = json.load(f)
                except Exception:
                    results = []
        
        completed_srno_set = {r["id"] for r in results if "id" in r}
        total_items_to_crawl = len(all_items)
        
        for idx, item in enumerate(all_items, start=1):
            srno = item.get("jisCntntsSrno")
            title = item.get("estbrlNm", "").strip()
            
            if on_progress:
                on_progress(idx, total_items_to_crawl, title)
                
            if srno in completed_srno_set:
                continue
                
            # 상세 기본정보 조회
            try:
                base_info = self.client.get_base_info(srno)
            except Exception as e:
                base_info = {}
                
            # 본문 컨텍스트 조회
            knd_cd = item.get("estbrlDocTypCd") or base_info.get("estbrlDocTypCd", "")
            try:
                ctxt_resp = self.client.get_context(srno, knd_cd=knd_cd)
                xslt_doc = ctxt_resp.get("xsltDocument", "")
            except Exception as e:
                xslt_doc = ""
                
            # 파싱 및 정제
            parsed = parse_context_document(xslt_doc)
            
            # 디렉토리 경로 해결
            cl_code = item.get("estbrlClCtt") or base_info.get("estbrlClCtt", "")
            dir_path = self._resolve_directory_path(cl_code, dir_map)
            if not dir_path:
                dir_path = [cat_name]
                
            # 정형화된 JSON 객체 생성
            record = {
                "id": srno,
                "category": cat_name,
                "category_code": cl_ctt,
                "data_no": item.get("estbrlDataNo") or base_info.get("estbrlDataNo", ""),
                "title": title,
                "status": item.get("estbrlDvsCdNm") or ("현행" if (item.get("crntEstbrlYn") == "01" or item.get("crntEstbrlYn") == "Y") else "폐지"),
                "action_type": item.get("estbrlEntrvsStatCdNm") or base_info.get("estbrlEntrvsStatCdNm", ""),
                "promulgation_date": format_date(item.get("prmlgtYmd") or base_info.get("prmlgtYmd")),
                "enforcement_date": format_date(item.get("enfcYmd") or base_info.get("enfcYmd")),
                "abolition_date": format_date(base_info.get("estbrlAblYmd")),
                "department": base_info.get("mcncrDeptNm"),
                "directory_code": cl_code,
                "directory_path": dir_path,
                "history": parsed["history"],
                "articles": parsed["articles"],
                "supplementary": parsed["supplementary"],
                "content_text": parsed["content_text"],
                "content_html": parsed["content_html"]
            }
            results.append(record)
            completed_srno_set.add(srno)
            
            # 주기적 체크포인트 저장 (10건마다)
            if checkpoint_file and idx % 10 == 0:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                    
        # 완료 후 최종 체크포인트 저장
        if checkpoint_file:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
        return results
