import os
import re
import ssl
import json
import time
import html
import argparse
import urllib.request
from pathlib import Path
import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_EXCEL = Path(r"C:\Users\rawfu\OneDrive\Desktop\Family_DSLM\예규 및 선례 목록.xlsx")
DEFAULT_OUTPUT = BASE_DIR / "data" / "corpus" / "scourt_family_directives_precedents.json"

PORTAL_HOME = "https://portal.scourt.go.kr/pgp/index.on?m=PGP1051M01&l=N&c=900"
SEARCH_API = "https://portal.scourt.go.kr/pgp/pgp1051/selectRuleEstbrlPrcdtSrchRsltLst.on"
CTXT_API = "https://portal.scourt.go.kr/pgp/pgp1051/selectRuleEstbrlPrcdtCtxt.on"

STATUTE_PATTERNS = [
    r"가족관계(?:의)?\s*등록\s*등에\s*관한\s*법률\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"가족관계등록법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"가족관계(?:의)?\s*등록\s*등에\s*관한\s*규칙\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"가족관계등록규칙\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"민법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"가사소송법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"주민등록법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"국적법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"호적법\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?",
    r"(?:법|규칙)\s*제\d+(?:조의\d+|\s*조)(?:\s*제\d+항)?"
]

class ScourtPrecedentCrawler:
    def __init__(self, delay=0.2):
        self.delay = delay
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": PORTAL_HOME
        }
        self.session_established = False

    def init_session(self):
        if not self.session_established:
            req = urllib.request.Request(PORTAL_HOME, headers=self.headers)
            with self.opener.open(req, timeout=15) as res:
                if res.status == 200:
                    self.session_established = True
                    print("[ScourtCrawler] Session established successfully with portal.scourt.go.kr")

    def load_excel_items(self, excel_path: Path):
        if not excel_path.exists():
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")

        wb = openpyxl.load_workbook(str(excel_path), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        items = []
        for idx, r in enumerate(rows[1:], 1):
            if not r or not r[1]:
                continue
            raw_type = str(r[1]).strip()
            title = str(r[2]).strip() if r[2] else ""
            raw_no = str(r[3]).strip() if r[3] else ""
            enact_date = str(r[4]).strip() if r[4] else ""
            enforce_date = str(r[5]).strip() if len(r) > 5 and r[5] else ""
            status = str(r[6]).strip() if len(r) > 6 and r[6] else "현행"

            clean_no = re.sub(r'[^0-9\-]', '', raw_no)
            is_dir = "예규" in raw_type
            item_category = "가족관계등록예규" if is_dir else "가족관계등록선례"

            items.append({
                "excel_row": idx,
                "type": "예규" if is_dir else "선례",
                "category": item_category,
                "title": title,
                "raw_no": raw_no,
                "clean_no": clean_no,
                "enact_date": enact_date,
                "enforce_date": enforce_date,
                "status": status
            })

        print(f"[ScourtCrawler] Loaded {len(items)} items from {excel_path.name}")
        return items

    def search_item(self, item):
        self.init_session()
        clean_no = item["clean_no"]
        is_dir = item["type"] == "예규"

        # 1차: 발령번호 기반 검색
        candidates = self._do_search(estbrl_data_no=clean_no)
        matched = self._filter_best_match(candidates, item, is_dir)

        # 2차: 번호 매칭 실패 시 명칭(estbrlNm) 기반 검색
        if not matched and item["title"]:
            cand_title = self._do_search(estbrl_nm=item["title"])
            matched = self._filter_best_match(cand_title, item, is_dir)

        return matched

    def _do_search(self, estbrl_data_no="", estbrl_nm=""):
        payload = {
            "dma_searchParam": {
                "category": "ruleEstbrlPrcdt",
                "pageNo": "1",
                "pageSize": "50",
                "jisCntntsKndCd": "07",
                "initYn": "N",
                "dtlSrchYn": "Y",
                "searchRange": "all",
                "estbrlDataNo": estbrl_data_no,
                "estbrlNm": estbrl_nm,
                "sort": "$match(text_title_idx) desc, $relevance desc",
                "sortType": "정확도순"
            }
        }
        try:
            req = urllib.request.Request(SEARCH_API, data=json.dumps(payload).encode("utf-8"), headers=self.headers)
            with self.opener.open(req, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                return data.get("data", {}).get("dlt_ruleEstbrlPrcdtRslt", []) if data.get("data") else []
        except Exception as e:
            print(f"[Search Error] {e}")
            return []

    def _filter_best_match(self, candidates, item, is_dir):
        if not candidates:
            return None

        clean_no = item["clean_no"]
        filtered = []
        for c in candidates:
            cdcs = c.get("estbrlCdcsNm", "")
            c_no = re.sub(r'[^0-9\-]', '', c.get("estbrlDataNo", ""))
            
            # 번호가 다르면 제외
            if clean_no and c_no != clean_no:
                continue

            if is_dir and "예규" in cdcs and "가족" in cdcs:
                filtered.append(c)
            elif not is_dir and "선례" in cdcs and ("가족" in cdcs or "호적" in cdcs):
                filtered.append(c)

        if not filtered:
            # 완화된 분류 필터
            for c in candidates:
                c_no = re.sub(r'[^0-9\-]', '', c.get("estbrlDataNo", ""))
                if clean_no and c_no == clean_no:
                    cdcs = c.get("estbrlCdcsNm", "")
                    if is_dir and "예규" in cdcs:
                        filtered.append(c)
                    elif not is_dir and "선례" in cdcs:
                        filtered.append(c)

        if not filtered:
            return None

        if len(filtered) == 1:
            return filtered[0]

        # 제목 유사도 매칭
        best_cand = filtered[0]
        best_overlap = 0
        target_words = set(item["title"].split())
        for c in filtered:
            c_title = c.get("estbrlNm", "").replace("<strong>", "").replace("</strong>", "")
            c_words = set(c_title.split())
            overlap = len(target_words & c_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_cand = c

        return best_cand

    def fetch_full_text(self, jis_cntnts_srno):
        payload = {
            "dma_searchParam02": {
                "jisCntntsSrno": str(jis_cntnts_srno),
                "jisCntntsKndCd": "07",
                "docType": "estbrl",
                "chnchrYn": "N"
            }
        }
        try:
            req = urllib.request.Request(CTXT_API, data=json.dumps(payload).encode("utf-8"), headers=self.headers)
            with self.opener.open(req, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                ctxt_obj = data.get("data", {}).get("dma_ruleEstbrlPrcdtCtxt", {})
                xslt_doc = ctxt_obj.get("xsltDocument", "") or ctxt_obj.get("orgdocXmlCtt", "")
                return self._clean_html_text(xslt_doc)
        except Exception as e:
            print(f"[Ctxt Error {jis_cntnts_srno}] {e}")
            return ""

    def _clean_html_text(self, raw_html: str) -> str:
        if not raw_html:
            return ""

        # Remove script and style
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', raw_html, flags=re.IGNORECASE)
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)

        # Replace block tags with newlines
        text = re.sub(r'</?(?:p|div|h\d|tr|li|br)[^>]*>', '\n', text, flags=re.IGNORECASE)

        # Remove remaining tags
        text = re.sub(r'<[^>]+>', '', text)

        # Unescape HTML entities
        text = html.unescape(text)

        # Normalize spaces while preserving meaningful paragraphs
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if s:
                lines.append(s)

        return "\n\n".join(lines)

    def extract_statutes(self, text: str):
        found = set()
        for pat in STATUTE_PATTERNS:
            for m in re.finditer(pat, text):
                cleaned = re.sub(r'\s+', ' ', m.group(0)).strip()
                found.add(cleaned)
        return sorted(list(found))

    def run(self, excel_path: Path = DEFAULT_EXCEL, output_path: Path = DEFAULT_OUTPUT, limit: int = None):
        print(f"================================================================")
        print(f" [ScourtPrecedentCrawler] Starting Directive & Precedent TDM")
        print(f" Excel Source: {excel_path}")
        print(f" Target Output: {output_path}")
        print(f"================================================================")

        items = self.load_excel_items(excel_path)
        if limit and limit > 0:
            items = items[:limit]
            print(f"[ScourtCrawler] Limiting to first {limit} items for testing.")

        corpus = []
        total = len(items)
        success_count = 0
        fail_count = 0

        for idx, it in enumerate(items, 1):
            title = it["title"]
            clean_no = it["clean_no"]
            item_type = it["type"]

            prefix = f"[{idx}/{total}] [{item_type} 제{clean_no}호]"
            matched = self.search_item(it)

            if matched:
                srno = matched.get("jisCntntsSrno")
                m_title = matched.get("estbrlNm", "").replace("<strong>", "").replace("</strong>", "").strip() or title
                m_no = matched.get("estbrlDataNo", "").replace("<strong>", "").replace("</strong>", "").strip() or clean_no
                m_cdcs = matched.get("estbrlCdcsNm", item_type)
                enact_ymd = matched.get("prmlgtYmd") or matched.get("estbrlEnactYmd") or it["enact_date"]
                enforce_ymd = matched.get("enfcYmd") or it["enforce_date"]
                status_nm = matched.get("estbrlEntrvsStatNm") or it["status"] or "현행"

                full_text = self.fetch_full_text(srno)
                if not full_text:
                    full_text = f"제목: {m_title}\n발령번호: {item_type} 제{m_no}호\n발령일자: {enact_ymd}\n\n(본문 조회 내용 공백)"

                statutes = self.extract_statutes(full_text)

                doc_id = f"SCOURT-{'DIR' if item_type == '예규' else 'PREC'}-{m_no}"
                formatted_title = f"[{m_cdcs} 제{m_no}호] {m_title}"
                source_label = f"대법원 사법정보공개포털 ({m_cdcs} 제{m_no}호, SRNO:{srno})"

                content_block = (
                    f"【{m_cdcs} 제{m_no}호】 {m_title}\n"
                    f"• 발령일자: {enact_ymd} | 시행일자: {enforce_ymd} | 상태: {status_nm}\n"
                    f"• 관련 법령 조문: {', '.join(statutes) if statutes else '기본 가족관계등록법령'}\n\n"
                    f"{full_text}"
                )

                chunk = {
                    "id": doc_id,
                    "title": formatted_title,
                    "category": it["category"],
                    "source": source_label,
                    "content": content_block,
                    "metadata": {
                        "item_type": item_type,
                        "data_no": m_no,
                        "raw_no": it["raw_no"],
                        "jis_srno": srno,
                        "enact_date": enact_ymd,
                        "enforce_date": enforce_ymd,
                        "current_status": status_nm,
                        "legal_articles": statutes,
                        "char_length": len(content_block),
                        "crawled_at": int(time.time())
                    }
                }
                corpus.append(chunk)
                success_count += 1
                print(f"{prefix} SUCCESS -> SRNO:{srno}, Len:{len(content_block)} chars, LawTags:{len(statutes)}")
            else:
                fail_count += 1
                print(f"{prefix} FAILED to match portal records. (Title: {title[:25]}...)")

            time.sleep(self.delay)

        # Output save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=2)

        file_size_kb = output_path.stat().st_size / 1024
        print(f"\n================================================================")
        print(f" [ScourtPrecedentCrawler] Mining Complete!")
        print(f" Total Target: {total} items")
        print(f" Success: {success_count} items ({success_count/total*100:.1f}%)")
        print(f" Failed: {fail_count} items")
        print(f" Output File: {output_path} ({file_size_kb:.1f} KB)")
        print(f"================================================================")
        return corpus

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="대법원 가족관계등록 규칙·예규·선례 TDM 크롤러")
    parser.add_argument("--excel", type=str, default=str(DEFAULT_EXCEL), help="엑셀 파일 경로")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="출력 JSON 경로")
    parser.add_argument("--limit", type=int, default=None, help="테스트 수집 제한 수")
    parser.add_argument("--delay", type=float, default=0.2, help="요청 간 딜레이(초)")
    args = parser.parse_args()

    crawler = ScourtPrecedentCrawler(delay=args.delay)
    crawler.run(excel_path=Path(args.excel), output_path=Path(args.output), limit=args.limit)
